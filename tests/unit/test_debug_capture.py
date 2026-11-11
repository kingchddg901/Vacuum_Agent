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

from homeassistant.exceptions import ServiceValidationError

from custom_components.eufy_vacuum.debug_capture import (
    TARGET_ALL_FLAGGED,
    TARGET_EVERYTHING,
    DebugCapture,
    build_debug_switch,
    build_debug_target_select,
    configure,
    debug_traceable,
    get_capture,
    register_debug_services,
    render_text,
    traceable_services,
)

# The tests configure the recorder like a drop-in would — a package logger + areas.
PKG = "custom_components.eufy_vacuum"
TEST_AREAS = {"map": (".mapping", ".map_source"), "learning": (".learning",)}


@pytest.fixture(autouse=True)
def _configured():
    """Point the (module-global) recorder at a known logger tree for each test, and put
    every scrap of global state back afterwards.

    R2-TEST-1. PKG is the REAL integration logger, and tests here mutate it directly —
    test_stop_restores_logger_and_keeps_records sets it to WARNING as its setup, to prove
    stop() restores a pre-existing level. It never undid that, so the package logger stayed
    at WARNING for the whole session and every later test that expected an INFO record via
    caplog got nothing: caplog.set_level() raises the ROOT logger and its own handler, but
    the record is already discarded at the SOURCE logger, which is upstream of both.

    It surfaced as tests/adapters/test_brand_selection.py failing with an empty caplog under
    `pytest tests/unit tests/integration tests/adapters` while a bare `pytest tests` stayed
    green — alphabetical collection runs tests/adapters BEFORE tests/unit gets to poison it.
    A pass/fail that depends on argument order is worth more than the one assertion it broke.

    `configure()` also writes module globals in the production module (_PACKAGE_LOGGER,
    _AREAS), retargeting the recorder process-wide; restored here for the same reason."""
    import custom_components.eufy_vacuum.debug_capture as _dc

    logger = logging.getLogger(PKG)
    prior_level, prior_propagate = logger.level, logger.propagate
    prior_pkg, prior_areas = _dc._PACKAGE_LOGGER, _dc._AREAS
    configure(PKG, TEST_AREAS)
    try:
        yield
    finally:
        logger.setLevel(prior_level)
        logger.propagate = prior_propagate
        _dc._PACKAGE_LOGGER, _dc._AREAS = prior_pkg, prior_areas


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


def test_stop_clears_run_metadata_so_a_later_status_is_honest(capture):
    """[RP-039/RF-33] stop() used to reset _ring/_passthrough/_prior_level/
    _prior_propagate/_logger_name but NOT _started_at/_areas/_targets, so a
    status() call made AFTER stop (the switch's extra_state_attributes, the
    debug_capture_status service) unconditionally reported the PREVIOUS run's
    start_at/areas/services alongside active:False."""
    capture.start(areas=["map"], services=["svc_demo"])
    capture.stop()
    later = capture.status()  # a call made well after stop, not stop()'s own return
    assert later["active"] is False
    assert later["started_at"] is None
    assert later["areas"] == []
    assert later["services"] == []


def test_resolve_areas_rejects_unknown_area(capture):
    """[RP-039/RF-33] An unrecognized area name must refuse loudly (listing the
    valid keys) instead of silently falling through to a near-certainly-wrong
    `.{area}` logger substring guess."""
    with pytest.raises(ServiceValidationError, match="learning|map"):
        capture.start(areas=["not_a_real_area"])
    # The failed start must not have left the capture half-armed.
    assert capture.active is False


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


def test_write_dump_filenames_are_unique_within_the_same_second(tmp_path):
    """[RP-039/RF-33] _write_dump used second-precision timestamps only, so two
    dumps within the same second silently overwrote each other. A millisecond
    component + a monotonic counter must guarantee a unique path every call."""
    from unittest.mock import MagicMock

    from custom_components.eufy_vacuum.debug_capture import _write_dump

    hass = MagicMock()
    hass.config.path.return_value = str(tmp_path)
    records = [{"seq": 1, "t": 0.0, "level": "DEBUG", "logger": "x", "message": "hi"}]

    paths = {_write_dump(hass, "eufy_vacuum", records) for _ in range(20)}
    assert len(paths) == 20, f"filename collision(s): {paths}"


@pytest.mark.asyncio
async def test_switch_turn_off_cancels_a_service_armed_autostop(global_capture, hass):
    """[RP-039/RF-16] A debug_capture_start service call with max_minutes arms an
    auto-stop timer; flipping the DebugCaptureSwitch off directly (not via the
    service layer) must cancel that SAME timer -- previously the switch had no
    access to the service handler's own (closure-local) cancel handle, so a
    service-armed auto-stop kept running (and could force-stop a LATER session
    the user started after manually stopping the first one)."""
    register_debug_services(hass, domain="eufy_vacuum")
    await hass.services.async_call(
        "eufy_vacuum", "debug_capture_start", {"max_minutes": 30}, blocking=True,
    )
    assert global_capture._autostop_cancel is not None, "auto-stop was not armed"

    sw = build_debug_switch(hass, domain="eufy_vacuum")
    sw.async_write_ha_state = MagicMock()
    await sw.async_turn_off()

    assert global_capture._autostop_cancel is None, (
        "switch turn_off did not cancel the service-armed auto-stop timer"
    )


@pytest.mark.asyncio
async def test_autostop_joins_entry_unload_ledger(global_capture, hass):
    """[RP-039/RF-16] Direct template: MS-1's own shape (monkeypatch/arm a
    long-running timer, assert it's ledgered, simulate teardown, assert the
    ledger is empty and the cancel fired) applied to the auto-stop timer's
    entry.async_on_unload join -- so a mid-capture entry reload/unload cancels
    it instead of leaving it armed against a torn-down hass."""
    from pytest_homeassistant_custom_component.common import MockConfigEntry

    entry = MockConfigEntry(domain="eufy_vacuum")
    entry.add_to_hass(hass)

    register_debug_services(hass, domain="eufy_vacuum")
    await hass.services.async_call(
        "eufy_vacuum", "debug_capture_start", {"max_minutes": 30}, blocking=True,
    )
    assert global_capture._autostop_cancel is not None, "auto-stop was not armed"
    assert entry._on_unload, "auto-stop cancel was not joined to the entry's ledger"

    # Simulate HA's own ConfigEntry._async_process_on_unload: pop + call LIFO.
    undo = entry._on_unload.pop()
    result = undo()
    if asyncio.iscoroutine(result):
        await result

    assert global_capture._autostop_cancel is None, (
        "the entry-unload ledger did not cancel the auto-stop timer"
    )


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


def test_redaction_masks_secrets_in_exc_info(capture):
    """[RP-004/DR-DBG-1] A traceback gets the SAME masking as a message -- the
    dump is safe to hand to a maintainer even when the secret rode an exception."""
    capture.start()
    logger = logging.getLogger(f"{PKG}.mapping.x")
    try:
        raise ValueError("auth failed for token=abc123secret retrying")
    except ValueError:
        logger.debug("handshake failed with token=abc123secret", exc_info=True)
    record = capture.records()[0]
    assert "abc123secret" not in record["message"]
    assert "abc123secret" not in record["exc"]
    assert "«redacted»" in record["exc"]
    text = render_text(capture.records())
    assert "abc123secret" not in text


def test_exc_info_is_capped_and_elided(capture):
    """[RP-004/DR-DBG-1] An oversized traceback is capped like a message, not a
    free multi-MB pass into the dump."""
    capture.start()
    logger = logging.getLogger(f"{PKG}.mapping.x")
    try:
        raise RuntimeError("payload=" + "A" * 50000)
    except RuntimeError:
        logger.debug("dumping payload", exc_info=True)
    record = capture.records()[0]
    assert len(record["exc"]) < 50000
    assert "elided" in record["exc"]
    text = render_text(capture.records())
    assert len(text) < 50000
    assert "elided" in text


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


# ---------------------------------------------------------------------------
# [DBG-SVC] the four services, end to end through hass.services
#
# These are the whole user-facing surface of the flight recorder, and the
# RESPONSE is the product: `supports_response=True` on all four, and the forum
# post that documents the feature describes those payloads. A handler that works
# but answers the wrong shape is a published false claim, not a cosmetic bug.
# ---------------------------------------------------------------------------

async def test_dbgsvc1_start_then_status_then_stop_round_trips(hass):
    """[DBG-SVC-1] The ordinary session: start, look, stop.

    Each response is asserted for the field a user reads, not merely for being a
    dict. `status` additionally carries `traceable`, the list of services the
    recorder can annotate -- it is computed separately from the capture's own
    status and merged in, so a status that lost it would still look healthy.
    """
    register_debug_services(hass, domain="eufy_vacuum")

    started = await hass.services.async_call(
        "eufy_vacuum", "debug_capture_start", {}, blocking=True,
        return_response=True,
    )
    assert started.get("active") is True, "start did not report an active capture"

    live = await hass.services.async_call(
        "eufy_vacuum", "debug_capture_status", {}, blocking=True,
        return_response=True,
    )
    assert live.get("active") is True
    assert "traceable" in live, (
        "status lost the traceable-service list, which is merged in separately "
        "from the capture's own status"
    )

    stopped = await hass.services.async_call(
        "eufy_vacuum", "debug_capture_stop", {}, blocking=True,
        return_response=True,
    )
    assert "captured" in stopped, (
        "stop must report how much it caught -- that number is what tells the "
        "user whether the window they chose was the right one"
    )

    # STOP'S OWN RESPONSE DESCRIBES THE RUN THAT JUST ENDED, deliberately: it is
    # read before the run's fields are reset, so `active` is still True in it.
    # Whether the capture really stopped is a question for the NEXT status call,
    # and the code comment makes that the contract -- "a LATER status() call must
    # not go on reporting a previous run's start_at/areas/services alongside
    # active:False". So that is what is asserted.
    after = await hass.services.async_call(
        "eufy_vacuum", "debug_capture_status", {}, blocking=True,
        return_response=True,
    )
    assert after.get("active") is False, "stop left the capture running"
    assert not after.get("started_at"), (
        "a stopped capture still reports the previous run's started_at"
    )


async def test_dbgsvc2_an_armed_auto_stop_fires_and_stops_the_capture(hass):
    """[DBG-SVC-2] `max_minutes` is the guard against a capture left running.

    A debug capture holds the package logger at DEBUG with propagate off. Left
    armed, it quietly suppresses the user's own log for the life of the process --
    the same failure the clean-order lock exists to prevent elsewhere in this
    repo. `max_minutes` is the promise that it stops by itself.

    The timer is driven by moving the clock rather than waiting, and the
    assertion is the OBSERVABLE end state: the capture is no longer active.

    THIS TEST HOLDS THE FIRING, NOT THE ARMING, and the ablation is what drew the
    line. Replacing `capture.arm_autostop(async_call_later(...))` with a bare
    `async_call_later(...)` leaves this GREEN -- the timer is scheduled either way
    and fires on the clock change; `arm_autostop` stores the CANCEL handle, so it
    governs whether a stop or an entry unload can call the timer off. That half is
    held by `test_autostop_joins_entry_unload_ledger` and
    `test_switch_turn_off_cancels_a_service_armed_autostop`, both of which did go
    red on that mutation. Dropping `if minutes:` reddens this one.
    """
    from datetime import timedelta
    import homeassistant.util.dt as dt_util
    from pytest_homeassistant_custom_component.common import async_fire_time_changed

    register_debug_services(hass, domain="eufy_vacuum")

    started = await hass.services.async_call(
        "eufy_vacuum", "debug_capture_start", {"max_minutes": 1}, blocking=True,
        return_response=True,
    )
    assert started.get("auto_stop_minutes") == 1, (
        "the response did not tell the user the capture is on a timer: %r"
        % (started,)
    )

    async_fire_time_changed(hass, dt_util.utcnow() + timedelta(seconds=61))
    await hass.async_block_till_done()

    after = await hass.services.async_call(
        "eufy_vacuum", "debug_capture_status", {}, blocking=True,
        return_response=True,
    )
    assert after.get("active") is False, (
        "the auto-stop never fired; the logger stays at DEBUG with propagate off "
        "for the life of the process"
    )


async def test_dbgsvc3_dump_writes_a_file_by_default_and_can_be_told_not_to(
    hass, tmp_path, monkeypatch
):
    """[DBG-SVC-3] `write_file` DEFAULTS TO TRUE, and that default is the feature.

    The point of the recorder is handing someone a file: a user who runs the
    service with no options should get something they can attach to an issue
    rather than a JSON blob in the developer-tools response pane.

    ⚠ THE DEFAULT IS DECLARED TWICE AND ONLY ONE COPY CAN APPLY. Measured:
    flipping the handler's `call.data.get("write_file", True)` to False changes
    NOTHING, because `vol.Optional("write_file", default=True)` in `_DUMP_SCHEMA`
    fills the key on every validated call -- the handler never sees it absent.
    Flipping the SCHEMA's default reddens this test exactly, so that is where the
    behaviour lives and what this test holds. The handler's fallback is reachable
    only by calling the coroutine directly with a bare dict, which nothing in
    production does. Same for `clear`.

    Both arms are asserted because the default is the claim: with `write_file`
    False there must be NO file key at all, not an empty one.
    """
    register_debug_services(hass, domain="eufy_vacuum")
    monkeypatch.setattr(hass.config, "config_dir", str(tmp_path))

    await hass.services.async_call(
        "eufy_vacuum", "debug_capture_start", {}, blocking=True,
        return_response=True,
    )
    logging.getLogger(f"{PKG}.mapping.inner").debug("something worth keeping")

    dumped = await hass.services.async_call(
        "eufy_vacuum", "debug_capture_dump", {}, blocking=True,
        return_response=True,
    )
    assert dumped.get("file"), (
        "an options-free dump wrote no file; the user is handed a response pane "
        "instead of something they can attach to an issue"
    )
    assert dumped["count"] == len(dumped["records"])

    no_file = await hass.services.async_call(
        "eufy_vacuum", "debug_capture_dump", {"write_file": False}, blocking=True,
        return_response=True,
    )
    assert "file" not in no_file, (
        "write_file=False still wrote a file: %r" % (no_file.get("file"),)
    )

    await hass.services.async_call(
        "eufy_vacuum", "debug_capture_stop", {}, blocking=True, return_response=True
    )


async def test_dbgsvc4_dump_with_clear_empties_the_buffer_it_just_reported(hass):
    """[DBG-SVC-4] `clear` happens AFTER the records are read, not before.

    The ordering is the whole claim: the response must still carry the records
    that were just discarded, otherwise "dump and clear" hands the user an empty
    file and throws away the evidence. A second dump then proves the buffer really
    is empty.
    """
    register_debug_services(hass, domain="eufy_vacuum")

    await hass.services.async_call(
        "eufy_vacuum", "debug_capture_start", {}, blocking=True, return_response=True
    )
    logging.getLogger(f"{PKG}.mapping.inner").debug("the only record")

    first = await hass.services.async_call(
        "eufy_vacuum", "debug_capture_dump",
        {"write_file": False, "clear": True}, blocking=True, return_response=True,
    )
    assert first["count"] >= 1, (
        "clear ran before the records were read -- the evidence is gone and the "
        "user has an empty dump"
    )

    second = await hass.services.async_call(
        "eufy_vacuum", "debug_capture_dump",
        {"write_file": False}, blocking=True, return_response=True,
    )
    assert second["count"] == 0, "clear did not empty the buffer"

    await hass.services.async_call(
        "eufy_vacuum", "debug_capture_stop", {}, blocking=True, return_response=True
    )


def test_dbgsvc5_clear_resets_the_ring_as_well_as_the_recent_window(capture):
    """[DBG-SVC-5] Two buffers, and both have to be emptied.

    The capture keeps a RING (the bounded history) and `_last` (the recent
    window). `clear()` empties both, and the ring's bookkeeping -- `seen` and
    `full` -- has to go back to zero with it: a ring reporting `full` over an
    empty record list makes the next status lie about how much was captured and
    makes eviction behave as though the buffer were already at capacity.

    Asserted through `status()` as well as `records()`, because the counters are
    what a user reads and they are a separate thing from the records themselves.
    """
    capture.start(capacity=4)
    for i in range(6):
        logging.getLogger(f"{PKG}.mapping.inner").debug("record %d", i)

    assert capture.records(), "nothing was captured; this test cannot see a clear"

    capture.clear()

    assert capture.records() == [], "records survived the clear"
    status = capture.status()
    assert not status.get("captured"), (
        "the ring still reports %r captured after a clear" % (status.get("captured"),)
    )


def test_dbgsvc6_the_span_summariser_truncates_and_survives_a_broken_repr():
    """[DBG-SVC-6] `_summarize` annotates spans, so it runs on arbitrary user data.

    It is called with whatever a traced service was handed. Three behaviours, and
    the last one is why it has a try at all:

      short values      pass through unchanged
      long values       are cut at the limit AND say how much was dropped
      an unreprable one degrades to a marker instead of raising

    THE "+N" SUFFIX IS ASSERTED, not just the length. A silent truncation looks
    identical to a short value in a dump, and someone reading that dump needs to
    know the rest existed -- a coordinate list cut at 300 characters with no
    marker reads as a complete short list.

    The raising object is a real shape: a class whose __repr__ fails is what a
    half-constructed object from a brand SDK looks like mid-exception, which is
    exactly when a trace is being read.
    """
    from custom_components.eufy_vacuum.debug_capture import _summarize

    assert _summarize({"x": 1}) == repr({"x": 1})

    # DERIVED, not hand-computed: repr() adds the surrounding quotes, so the
    # dropped count is 202 and not the 200 the string length suggests. Computing
    # it from repr() also keeps this correct if the 300-character limit moves.
    raw = "A" * 500
    dropped = len(repr(raw)) - 300
    long_text = _summarize(raw)
    assert len(long_text) < len(repr(raw)), "the value was not truncated"
    assert f"(+{dropped})" in long_text, (
        "a truncated value did not say how much was dropped: %r" % (long_text[-40:],)
    )

    class _Broken:
        def __repr__(self):
            raise RuntimeError("half-constructed")

    assert _summarize(_Broken()) == "<unreprable>", (
        "a broken repr escaped the summariser -- and it is called while a trace "
        "is being written, which is already an unhappy path"
    )


def test_dbgsvc7_redaction_pairs_can_be_replaced_and_restored():
    """[DBG-SVC-7] `configure_redaction` is the seam for a host with its own secrets.

    The file is written to be dropped into any integration, and the default
    redactors cover this one's shapes. A host with a different secret format
    replaces them; passing None restores the defaults. The restore half matters
    most -- without it, one integration configuring redaction would silently
    disarm the defaults for everything else in the process, since the list is
    module-global.

    The restore is asserted by BEHAVIOUR, on a message the defaults do redact,
    rather than by comparing the list to itself.
    """
    import re

    from custom_components.eufy_vacuum.debug_capture import (
        _redact,
        configure_redaction,
    )

    secretish = "token=abcdef0123456789abcdef0123456789"
    default_result = _redact(secretish)

    try:
        configure_redaction([(re.compile(r"banana"), "«fruit»")])
        assert _redact("a banana here") == "a «fruit» here", (
            "the replacement redactor never ran"
        )
        assert _redact(secretish) == secretish, (
            "replacing the redactors left a default one armed, so the set is "
            "additive rather than a replacement"
        )
    finally:
        configure_redaction(None)

    assert _redact(secretish) == default_result, (
        "None did not restore the defaults -- the module-global list stays as the "
        "last caller left it and every other consumer loses its redaction"
    )
