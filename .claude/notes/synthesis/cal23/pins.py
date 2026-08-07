"""CAL-23 pins — new public-contract tests against ErrorTracker
(``core/error_tracker.py``).

These are NOT part of the frozen legacy suite
(``tests/integration/test_core_error_tracker.py``) and are never written into
the repo — this file is dropped into a scratch environment at run time and
executed in place there.

Target, per the CAL-23 brief:
  (a) RECONSTRUCTION-NOTES.md's 3 declared low-confidence areas:
      - acknowledged-flag lifecycle on a fresh rising edge (PIN 1)
      - zero-value handling in the numeric attribute-code scan (PIN 2a/2b)
      - same-tick event ordering across primary/secondary channels (PIN 3)
  (b) DR-SECTION.md's central contracts, through the PUBLIC surface only:
      constructor, start/stop, hass state changes, time advancement for the
      grace window, and the public accessors / update-listener callback.

PIN DISCIPLINE (docs/testing/04): no ``._name`` access on the tracker
anywhere in this file. Every test drives ``ErrorTracker`` only through:
  - the constructor (``ErrorTracker(hass, runtime_manager=...)``)
  - ``start`` / ``stop``
  - ``harvest_active_run`` / ``peek_active_run`` / ``commit_active_run``
  - ``acknowledge``
  - ``add_update_listener``
  - ``get_record`` / ``get_active_run_latch`` / ``get_last_device_latch`` /
    ``recent_errors``
  - the free functions ``classify_error_code`` / ``error_source_for_code`` /
    ``error_label_key``
  - ``hass.states.async_set`` / ``async_fire_time_changed`` for wiring and
    timing
  - ``register_adapter_config`` for adapter config
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

import pytest

import homeassistant.util.dt as dt_util
from pytest_homeassistant_custom_component.common import async_fire_time_changed

from tests._factories import spec_manager

from custom_components.eufy_vacuum.adapters.registry import register_adapter_config
from custom_components.eufy_vacuum.core.error_tracker import (
    ErrorTracker,
    error_label_key,
)


# ---------------------------------------------------------------------------
# helpers (standalone — do not import anything from the frozen legacy suite)
# ---------------------------------------------------------------------------


def _make_tracker(hass):
    mgr = spec_manager()
    mgr.data = {}
    from unittest.mock import AsyncMock

    mgr.async_save = AsyncMock()
    return ErrorTracker(hass, runtime_manager=mgr), mgr


def _seed_active_job(mgr, vacuum_entity_id, *, job_id="j1", room_id=3,
                      started_minutes_ago=2, status="started"):
    started = (datetime.now(timezone.utc)
               - timedelta(minutes=started_minutes_ago)).isoformat()
    mgr.data["active_jobs"] = {
        vacuum_entity_id: {"6": {"job_id": job_id, "started_at": started,
                                  "status": status, "current_room_id": room_id}}}


# ---------------------------------------------------------------------------
# PIN 1 — LOW-CONFIDENCE #1: acknowledged-flag lifecycle on a fresh rising edge
# ---------------------------------------------------------------------------


async def test_pin_acknowledged_does_not_hide_a_fresh_rising_edge(hass):
    """RECONSTRUCTION-NOTES.md 'Doc was silent' #1 / lowest-confidence #1.

    Does ``acknowledged`` survive across a brand-new rising edge on the SAME
    latch, or get cleared? DR §3.1 documents that ``acknowledged`` is set by
    ``acknowledge()`` and says nothing about what a *later* rising edge does
    to it.

    Guarded behavior (the ORIGINAL implementation's actual contract, used
    here as ground truth): ``acknowledge()`` marks the latch
    ``acknowledged: True`` mid-run without touching ``errors[]``. A later
    fresh rising edge on the same latch extends it (new message / code /
    error_count) but never touches the ``acknowledged`` key while doing so —
    it is left exactly as ``acknowledge()`` left it, i.e. it survives.
    """
    t, mgr = _make_tracker(hass)
    vac = "vacuum.pin_ack"
    err = "sensor.pin_ack_err"
    register_adapter_config(vac, {
        "adapter_id": "t", "source": "t",
        "entities": {"error_message": err},
    })
    _seed_active_job(mgr, vac)
    hass.states.async_set(vac, "cleaning")
    hass.states.async_set(err, "unknown")
    t.start([vac])

    hass.states.async_set(err, "Stuck")
    await hass.async_block_till_done()
    assert t.get_active_run_latch(vac)["current_message"] == "Stuck"

    assert t.acknowledge(vac, scope="active_run") is True
    marked = t.get_active_run_latch(vac)
    assert marked["acknowledged"] is True
    assert marked["current_message"] == ""

    # A brand-new fault fires on the SAME latch (run still in flight).
    hass.states.async_set(err, "Cliff")
    await hass.async_block_till_done()

    latch = t.get_active_run_latch(vac)
    assert latch["current_message"] == "Cliff"
    assert latch["error_count"] == 2
    assert latch["acknowledged"] is True, (
        "a fresh rising edge cleared `acknowledged` -- it must be left "
        "exactly as acknowledge() set it"
    )

    t.stop()


# ---------------------------------------------------------------------------
# PIN 2 — LOW-CONFIDENCE #2: zero-value handling in the numeric code scan
# ---------------------------------------------------------------------------


async def test_pin_zero_valued_attribute_does_not_stop_the_code_scan(hass):
    """RECONSTRUCTION-NOTES.md ambiguity #2 (same-entity half).

    DR §4.1: "The first attribute holding a non-zero int wins; non-int
    values are skipped" + "0 is treated as 'no code captured'" is ambiguous
    about whether hitting a 0 STOPS the scan (reads None) or is SKIPPED
    (scan continues to the next declared attribute name). This pin encodes
    "continues" (reading (b) in RECONSTRUCTION-NOTES.md).
    """
    t, mgr = _make_tracker(hass)
    vac = "vacuum.pin_zero"
    err = "sensor.pin_zero_err"
    register_adapter_config(vac, {
        "adapter_id": "t", "source": "t",
        "entities": {"error_message": err},
        "error_tracking": {"error_code_attribute_names": ["a", "b"]},
    })
    _seed_active_job(mgr, vac)
    hass.states.async_set(vac, "cleaning")
    hass.states.async_set(err, "unknown")
    t.start([vac])

    hass.states.async_set(err, "Stuck", {"a": 0, "b": 77})
    await hass.async_block_till_done()

    latch = t.get_active_run_latch(vac)
    assert latch["current_code"] == 77, (
        "a captured 0 on the FIRST declared attribute name stopped the "
        "scan instead of continuing to the next declared name"
    )

    t.stop()


async def test_pin_zero_valued_entity_does_not_stop_the_code_scan(hass):
    """RECONSTRUCTION-NOTES.md ambiguity #2 (cross-entity half).

    DR §4.1: the error_message entity's attributes are checked first, then
    the vacuum entity's. A captured 0 on the error_message entity must not
    stop the scan before it reaches the vacuum entity's own attributes.
    """
    t, mgr = _make_tracker(hass)
    vac = "vacuum.pin_zero2"
    err = "sensor.pin_zero2_err"
    register_adapter_config(vac, {
        "adapter_id": "t", "source": "t",
        "entities": {"error_message": err},
    })
    _seed_active_job(mgr, vac)
    hass.states.async_set(vac, "cleaning", {"error_code": 55})
    hass.states.async_set(err, "unknown")
    t.start([vac])

    hass.states.async_set(err, "Stuck", {"error_code": 0})
    await hass.async_block_till_done()

    latch = t.get_active_run_latch(vac)
    assert latch["current_code"] == 55, (
        "a captured 0 on the error_message entity stopped the scan before "
        "reaching the vacuum entity's own attributes"
    )

    t.stop()


# ---------------------------------------------------------------------------
# PIN 3 — LOW-CONFIDENCE #3: same-tick primary/secondary event ordering
# ---------------------------------------------------------------------------


async def test_pin_primary_edge_arriving_after_secondary_cancels_the_grace_window(hass):
    """RECONSTRUCTION-NOTES.md lowest-confidence #3.

    Regardless of whether the implementation wires one shared subscription
    or two independent ones, DR §5.5 requires: "While pending: a real
    rising edge on the primary channel cancels the timer; no placeholder is
    ever recorded in that case."

    This has to be checked with the primary channel back at a NON-error
    value by the time the grace window would have expired -- otherwise
    §5.5's separate expiry-time recheck ("if it now holds a real error, do
    nothing") independently suppresses the placeholder and the timer being
    left uncancelled is unobservable. So: vacuum flips to "error" (arms the
    timer, primary not yet error); the real message arrives immediately
    after (should cancel the timer) and then itself recovers before the
    window elapses -- the ONLY thing that can still stand between "no
    placeholder" and "a stale placeholder edge appended after the real one"
    at that point is whether the timer was actually cancelled when the real
    message first arrived.
    """
    t, mgr = _make_tracker(hass)
    vac = "vacuum.pin_tick"
    err = "sensor.pin_tick_err"
    register_adapter_config(vac, {
        "adapter_id": "t", "source": "t",
        "entities": {"error_message": err},
    })
    _seed_active_job(mgr, vac)
    hass.states.async_set(vac, "cleaning")
    hass.states.async_set(err, "unknown")
    t.start([vac])

    try:
        # Vacuum flips to "error" (arms the grace timer -- primary not yet
        # error), immediately followed by the REAL message arriving...
        hass.states.async_set(vac, "error")
        hass.states.async_set(err, "Stuck")
        await hass.async_block_till_done()

        latch = t.get_active_run_latch(vac)
        assert latch is not None
        assert latch["current_message"] == "Stuck", "the real message did not win"
        assert latch["error_count"] == 1, "the secondary channel produced its own edge too"

        # ...and then recovers, while the vacuum entity is STILL "error".
        # If the grace timer from the very first event was never actually
        # cancelled, it is still pending right now.
        hass.states.async_set(err, "unknown")
        await hass.async_block_till_done()
        assert t.get_active_run_latch(vac)["recovered"] is True

        # Advance well past the default 5s grace window.
        async_fire_time_changed(hass, dt_util.utcnow() + timedelta(seconds=6))
        await hass.async_block_till_done()

        latch = t.get_active_run_latch(vac)
        assert latch["error_count"] == 1, (
            "a grace timer that should have been cancelled when the real "
            "message first arrived fired anyway and appended a stale "
            "placeholder edge onto an already-recovered latch"
        )
        assert latch["recovered"] is True
    finally:
        t.stop()


# ---------------------------------------------------------------------------
# PIN 4 — DR §5.5/§7 central contract: negative grace_window_seconds
# ---------------------------------------------------------------------------


async def test_pin_negative_grace_window_seconds_fires_almost_immediately(hass):
    """RECONSTRUCTION-NOTES.md 'Doc was silent' #3.

    DR §5.5/§7 declare an explicit 0 and "not declared" but say nothing
    about a declared NEGATIVE grace_window_seconds. The original clamps a
    negative value to the floor of the underlying scheduling primitive
    (fires on the very next tick, same as an explicit 0) rather than to the
    documented 5s default.
    """
    t, mgr = _make_tracker(hass)
    vac = "vacuum.pin_neggrace"
    err = "sensor.pin_neggrace_err"
    register_adapter_config(vac, {
        "adapter_id": "t", "source": "t",
        "entities": {"error_message": err},
        "vocabulary": {"not_error_sentinels": ["none", "normal"]},
        "error_tracking": {"grace_window_seconds": -10},
    })
    _seed_active_job(mgr, vac)
    hass.states.async_set(vac, "cleaning")
    hass.states.async_set(err, "none")
    t.start([vac])

    try:
        hass.states.async_set(vac, "error")
        await hass.async_block_till_done()

        # Comfortably past an ~0s clamp, comfortably short of a 5s default.
        async_fire_time_changed(hass, dt_util.utcnow() + timedelta(seconds=1))
        await hass.async_block_till_done()

        latch = t.get_active_run_latch(vac)
        assert latch is not None, (
            "a negative grace_window_seconds was clamped to the 5s default "
            "instead of firing almost immediately"
        )
        assert latch["current_message"] == "Unknown error during run"
    finally:
        t.stop()


# ---------------------------------------------------------------------------
# PIN 5 — DR §5.5/§7 central contract: explicit 0 grace window
# ---------------------------------------------------------------------------


async def test_pin_explicit_zero_grace_window_is_honored_not_treated_as_unset(hass):
    """DR §5.5/§7: an explicit 0 fires on the very next event-loop tick
    rather than being read as "unset" (which would fall back to the 5s
    default)."""
    t, mgr = _make_tracker(hass)
    vac = "vacuum.pin_zerograce"
    err = "sensor.pin_zerograce_err"
    register_adapter_config(vac, {
        "adapter_id": "t", "source": "t",
        "entities": {"error_message": err},
        "vocabulary": {"not_error_sentinels": ["none", "normal"]},
        "error_tracking": {"grace_window_seconds": 0},
    })
    _seed_active_job(mgr, vac)
    hass.states.async_set(vac, "cleaning")
    hass.states.async_set(err, "none")
    t.start([vac])

    try:
        hass.states.async_set(vac, "error")
        await hass.async_block_till_done()

        async_fire_time_changed(hass, dt_util.utcnow() + timedelta(seconds=1))
        await hass.async_block_till_done()

        latch = t.get_active_run_latch(vac)
        assert latch is not None, "explicit 0 was read as unset and fell back to the 5s default"
        assert latch["current_message"] == "Unknown error during run"
    finally:
        t.stop()


# ---------------------------------------------------------------------------
# PIN 6 — DR §4.3 central contract: error_label_key value type discipline
# ---------------------------------------------------------------------------


def test_pin_error_label_key_requires_a_real_non_empty_string_value(hass):
    """DR §4.3 says the declared ``error_label_keys`` map "accepts both ints
    and lowercase enum strings" for its KEYS but is silent on what a
    non-string VALUE should resolve to. The original treats an entry whose
    stored value is not a non-empty string as equivalent to no label at all
    (None) -- it never coerces a value into a string.
    """
    vac = "vacuum.pin_label"
    register_adapter_config(vac, {
        "adapter_id": "t", "source": "t",
        "error_tracking": {"error_label_keys": {"70": 12345, "71": ""}},
    })
    assert error_label_key(vac, 70) is None, (
        "a non-string label value (12345) was coerced into a fake i18n key"
    )
    assert error_label_key(vac, 71) is None, (
        "an empty-string label value was returned as if it were a real key"
    )
    # control: a real string value still resolves.
    register_adapter_config(vac, {
        "adapter_id": "t", "source": "t",
        "error_tracking": {"error_label_keys": {"70": "fault.seventy"}},
    })
    assert error_label_key(vac, 70) == "fault.seventy"


# ---------------------------------------------------------------------------
# PIN 7 — DR §3.1/§5.1 central contract: stored message text is verbatim
# ---------------------------------------------------------------------------


async def test_pin_primary_channel_message_text_is_captured_verbatim(hass):
    """DR §3.1's ``current_message`` / ``errors[].message`` fields are
    documented as "Latest error text" with no stated normalization step.
    The original stores exactly what the primary channel's state text was
    -- it strips only for the SEPARATE "looks like an error" comparison
    (DR §5.1), never for the stored message itself.
    """
    t, mgr = _make_tracker(hass)
    vac = "vacuum.pin_ws"
    err = "sensor.pin_ws_err"
    register_adapter_config(vac, {
        "adapter_id": "t", "source": "t",
        "entities": {"error_message": err},
    })
    _seed_active_job(mgr, vac)
    hass.states.async_set(vac, "cleaning")
    hass.states.async_set(err, "unknown")
    t.start([vac])

    hass.states.async_set(err, "  Stuck in dock  ")
    await hass.async_block_till_done()

    latch = t.get_active_run_latch(vac)
    assert latch["current_message"] == "  Stuck in dock  ", (
        f"the stored message was reformatted: {latch['current_message']!r}"
    )
    assert t.get_record(vac)["last_device_error"]["message"] == "  Stuck in dock  "

    t.stop()


# ---------------------------------------------------------------------------
# PIN 8 — DR §6.2 central contract: commit_active_run identity gate
# ---------------------------------------------------------------------------


async def test_pin_commit_active_run_refuses_a_stale_peek(hass):
    """DR §6.2: commit_active_run clears the latch a prior peek_active_run
    returned ONLY if the live latch is still the same one (identity ==
    first_seen_at + error_count equality). If a new edge extended the latch
    since the peek, commit must leave it untouched and return False."""
    t, mgr = _make_tracker(hass)
    vac = "vacuum.pin_commit"
    err = "sensor.pin_commit_err"
    register_adapter_config(vac, {
        "adapter_id": "t", "source": "t",
        "entities": {"error_message": err},
    })
    _seed_active_job(mgr, vac)
    hass.states.async_set(vac, "cleaning")
    hass.states.async_set(err, "unknown")
    t.start([vac])

    hass.states.async_set(err, "Stuck")
    await hass.async_block_till_done()
    peeked = t.peek_active_run(vac, "j1")
    assert peeked is not None

    # The latch moves on before the caller commits.
    hass.states.async_set(err, "Cliff")
    await hass.async_block_till_done()

    committed = t.commit_active_run(vac, peeked)
    assert committed is False, "commit cleared a latch that had moved on since the peek"

    live = t.get_active_run_latch(vac)
    assert live is not None, "the moved-on latch was destroyed anyway"
    assert live["error_count"] == 2
    assert live["current_message"] == "Cliff"

    t.stop()


# ---------------------------------------------------------------------------
# PIN 9 — DR §6.2 central contract: harvest_active_run job_id tolerance
# ---------------------------------------------------------------------------


async def test_pin_harvest_active_run_ignores_a_job_id_mismatch(hass):
    """DR §6.2: a mismatched job_id does NOT suppress harvest_active_run's
    return -- the latch comes back regardless, and is cleared either way."""
    t, mgr = _make_tracker(hass)
    vac = "vacuum.pin_harvest"
    err = "sensor.pin_harvest_err"
    register_adapter_config(vac, {
        "adapter_id": "t", "source": "t",
        "entities": {"error_message": err},
    })
    _seed_active_job(mgr, vac, job_id="j1")
    hass.states.async_set(vac, "cleaning")
    hass.states.async_set(err, "unknown")
    t.start([vac])

    hass.states.async_set(err, "Stuck")
    await hass.async_block_till_done()

    harvested = t.harvest_active_run(vac, "totally-different-job-id")
    assert harvested is not None, "a job_id mismatch suppressed the harvest"
    assert harvested["current_message"] == "Stuck"
    assert t.get_active_run_latch(vac) is None

    t.stop()


# ---------------------------------------------------------------------------
# PIN 10 — DR §6.4 central contract: update-listener fan-out
# ---------------------------------------------------------------------------


async def test_pin_update_listener_fires_for_every_mutation_kind(hass):
    """DR §6.4: add_update_listener's callback is called with the affected
    vacuum_entity_id (one positional string, not zero) whenever that
    vacuum's latch state changes -- rising edge, falling edge, and
    acknowledge all share the same notify path."""
    t, mgr = _make_tracker(hass)
    vac = "vacuum.pin_listener"
    err = "sensor.pin_listener_err"
    register_adapter_config(vac, {
        "adapter_id": "t", "source": "t",
        "entities": {"error_message": err},
    })
    _seed_active_job(mgr, vac)
    hass.states.async_set(vac, "cleaning")
    hass.states.async_set(err, "unknown")
    t.start([vac])

    seen: list[str] = []
    t.add_update_listener(lambda vid: seen.append(vid))

    hass.states.async_set(err, "Stuck")     # rising edge
    await hass.async_block_till_done()
    hass.states.async_set(err, "unknown")   # falling edge
    await hass.async_block_till_done()
    t.acknowledge(vac, scope="last_device")  # acknowledge

    assert len(seen) >= 3, f"expected a notification per mutation, got {seen}"
    assert all(vid == vac for vid in seen)

    t.stop()


# ---------------------------------------------------------------------------
# PIN 11 — RECONSTRUCTION-NOTES.md 'Doc was silent' #8: read accessors never
# schedule a save
# ---------------------------------------------------------------------------


async def test_pin_read_accessors_never_schedule_a_save(hass):
    """get_record and the other three read accessors create the per-device
    record lazily (DR §6.5) but that lazy creation must NOT itself count as
    a mutation for save-scheduling purposes -- only the four explicitly
    listed mutation categories (DR §2: rising/falling edge, harvest, commit,
    acknowledge) schedule a save.

    Save scheduling is fire-and-forget (``call_soon_threadsafe`` +
    ``async_create_task`` per DR §2's thread-safety requirement), so this
    must drain the event loop with ``async_block_till_done`` before checking
    -- a scheduled-but-not-yet-run save would otherwise read as "never
    scheduled" by accident, not by contract.
    """
    t, mgr = _make_tracker(hass)
    vac = "vacuum.pin_read"

    t.get_record(vac)
    t.get_active_run_latch(vac)
    t.get_last_device_latch(vac)
    t.recent_errors(vac)
    t.recent_errors(vac, limit=3)
    await hass.async_block_till_done()

    mgr.async_save.assert_not_awaited()
