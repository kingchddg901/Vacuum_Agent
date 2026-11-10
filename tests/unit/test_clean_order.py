"""Device clean-order acquisition — the shape filter that makes the readback trustworthy.

WHY THESE ARE THE TESTS THAT MATTER
-----------------------------------
`vacuum.send_command` is SupportsResponse.NONE, so the reply is captured off a DEBUG log
line that does NOT say which command it answers. Everything therefore rests on
`is_clean_order` telling a real reply apart from routine poll traffic. If that filter is
wrong the sensor reports confident nonsense — the worst failure available here, because
it looks like a reading.

The inputs below are REAL decoded results captured from Ivy on 2026-08-19, not invented
shapes. `[0]` in particular is emitted by the device every poll tick (~15 s), and it is
the input that makes a naive "flat list of ints" filter red.
"""

from __future__ import annotations

import pytest

from custom_components.eufy_vacuum.clean_order.manager import (
    ORDER_SENTINEL,
    STATUS_NEVER_READ,
    STATUS_OK,
    STATUS_UNAVAILABLE,
    WRITE_OK,
    WRITE_REFUSED,
    WRITE_UNCONFIRMED,
    WRITE_UNSUPPORTED,
    CleanOrderManager,
    is_clean_order,
    parse_decoded_result,
)

#: Ivy's managed rooms on "Main floor" — the filter's vocabulary.
KNOWN = {17, 18, 20, 21, 22, 23, 24, 25, 26, 27}

PREFIX = "Decoded V1 message result: "

#: Every distinct shape observed across 53 real decoded results, plus the two real
#: clean-order replies. (payload, is_a_clean_order)
REAL_DECODED_SHAPES = [
    ("[27, 25, 23, 22]", True),                                  # our write, read back
    ("[24, 22, 25]", True),                                      # set via the vendor app
    ("[]", True),                                                # no order saved
    ("[0]", False),                                              # <- every poll tick
    ("[734826, 11824807500, 336, [1787200920]]", False),         # clean summary
    ("[[1787200920, 1787201244, 324, 6015000]]", False),         # clean record
    ("['ok']", False),                                           # a write ack
    ("[{'msg_ver': 2, 'state': 8, 'battery': 100}]", False),     # status
    ("[{'main_brush_work_time': 14848}]", False),                # consumables
    ("[{'start_hour': 22, 'end_hour': 8, 'enabled': 0}]", False),  # do-not-disturb
]


@pytest.mark.parametrize("payload,expected", REAL_DECODED_SHAPES)
def test_the_filter_admits_only_real_clean_orders(payload, expected):
    """Each real decoded shape is classified correctly."""
    result = parse_decoded_result(f"... {PREFIX}{payload}", PREFIX)
    assert result is not None, "the payload should have parsed"
    assert is_clean_order(result, KNOWN) is expected


def test_room_id_membership_is_what_rejects_the_poll_tick():
    """ABLATION: without the known-room-id check, `[0]` is accepted as an order.

    This is the test that proves the membership condition earns its place rather than
    reading as belt-and-braces. `[0]` arrives roughly every 15 seconds, so a filter
    weakened to a type check would report it as a clean order continuously.
    """
    zero = parse_decoded_result(f"... {PREFIX}[0]", PREFIX)

    # The real filter rejects it...
    assert is_clean_order(zero, KNOWN) is False

    # ...and the ablated filter — "a flat list of ints", membership removed — does not.
    ablated = isinstance(zero, list) and all(
        isinstance(x, int) and not isinstance(x, bool) for x in zero
    )
    assert ablated is True, (
        "if this ever goes False the ablation is no longer meaningful and the "
        "membership check may have become untestable"
    )


def test_booleans_are_not_room_ids():
    """`isinstance(True, int)` is True in Python, so `[True]` would sneak past a naive
    int check. It must not be read as room id 1."""
    assert is_clean_order([True], KNOWN | {1}) is False


def test_a_partially_known_list_is_rejected_whole():
    """One unknown id invalidates the reading — we never return a half-understood order,
    because a dropped room would silently reorder the rest."""
    assert is_clean_order([27, 25, 999], KNOWN) is False


def test_an_unparseable_payload_degrades_to_no_reading():
    """A format change upstream must yield None (→ `unavailable`), never an exception on
    a path a live run can touch."""
    assert parse_decoded_result(f"... {PREFIX}<not a literal>", PREFIX) is None


def test_a_line_that_is_not_a_decoded_result_is_ignored():
    assert parse_decoded_result("eufy_vacuum: something else entirely", PREFIX) is None


def test_ansi_wrapped_lines_parse():
    """HA's log endpoint wraps lines in colour codes; the real captures all carried them."""
    line = (
        "\x1b[36m2026-08-19 22:48:39.572 DEBUG (MainThread) "
        "[roborock.protocols.v1_protocol] Decoded V1 message result: "
        "[27, 25, 23, 22]\x1b[0m"
    )
    assert parse_decoded_result(line, PREFIX) == [27, 25, 23, 22]


def test_empty_vocabulary_cannot_validate_a_populated_order():
    """With no known room ids (map not ready) only `[]` can match, which is why the
    manager declines to read at all rather than accepting a list it cannot check."""
    assert is_clean_order([27, 25], set()) is False
    assert is_clean_order([], set()) is True


def test_never_read_is_distinct_from_an_empty_order():
    """An unread vacuum must not present as "no order saved". An empty order is a fact
    about the device; an unread one is the absence of a fact, and conflating them is the
    exact trap this subsystem exists to avoid."""
    assert STATUS_NEVER_READ != "ok"
    # [] is a legitimate ORDER value, so the status field — not the order — is what
    # carries "we have not looked yet".
    assert is_clean_order([], KNOWN) is True


# ---------------------------------------------------------------------------
# [CO-W] the WRITE — set_clean_sequence, model-gated, ack-verified
#
# This edits a PERSISTENT, MAP-LEVEL setting in the user's Roborock app: a saved
# sequence orders every start, including ones they begin from the vendor app, and it
# renders on that app's own Sequence screen. Every test below is guarding somebody
# else's data, not just our state.
# ---------------------------------------------------------------------------

_VAC = "vacuum.ivy"

_WRITE_CFG = {
    "enabled": True,
    "write": {
        "via": "v1_send_command",
        "service": {"domain": "vacuum", "service": "send_command"},
        "payload": {"command": "set_clean_sequence", "params": ORDER_SENTINEL},
        "clear": {"command": "set_clean_sequence", "params": []},
        "ack": {
            "via": "v1_debug_log",
            "equals": ["ok"],
            "source_logger": "test.v1",
            "decoded_prefix": PREFIX,
        },
    },
}


class _FakeManager:
    """Just enough core manager for CleanOrderManager: config, rooms, service calls."""

    def __init__(self, cfg, known=KNOWN):
        self._cfg = cfg
        self._known = known
        self.calls = []
        self.hass = self

        class _Services:
            def __init__(self, outer):
                self._outer = outer

            async def async_call(self, domain, service, data, blocking=False):
                self._outer.calls.append((domain, service, data))

        self.services = _Services(self)

    # -- the bits CleanOrderManager reaches for -------------------------------
    def resolve_active_map_id(self, vacuum_entity_id):
        return "1"

    def get_managed_rooms(self, *, vacuum_entity_id, map_id):
        return {"rooms": {str(r): {} for r in self._known}}


def _mgr(cfg=_WRITE_CFG, known=KNOWN, monkeypatch=None):
    core = _FakeManager(cfg, known)
    com = CleanOrderManager(manager=core)
    if monkeypatch is not None:
        monkeypatch.setattr(com, "_config", lambda vacuum_entity_id: cfg)
    return com, core


def test_cow1_the_order_sentinel_is_substituted_WHOLESALE(monkeypatch):
    """[CO-W1] RED IF $order IS STRING-INTERPOLATED INSTEAD OF REPLACED.

    Chris, 2026-08-20: "$order is replaced WHOLESALE (not string-interpolated) so the
    list stays a list -- a template that stringifies its substitution is how a list
    becomes "[27, 25]" on the wire."

    A stringified payload would very likely still ACK, because the device answers the
    command not the argument -- so this failure would present as a confirmed write that
    did nothing. Asserting the TYPE is the only thing that catches it.
    """
    com, core = _mgr(monkeypatch=monkeypatch)

    result = _run(com.async_write(_VAC, [27, 25, 23]))

    assert core.calls, "nothing was sent"
    _, _, data = core.calls[-1]
    assert data["command"] == "set_clean_sequence"
    assert data["params"] == [27, 25, 23]
    assert isinstance(data["params"], list), (
        f"params reached the wire as {type(data['params']).__name__}: {data['params']!r}"
    )
    # no ack was emitted on the fake logger -> unconfirmed, never OK
    assert result["status"] == WRITE_UNCONFIRMED


def test_cow2_an_unacked_write_is_UNCONFIRMED_never_ok(monkeypatch):
    """[CO-W2] RED IF AN UNVERIFIED WRITE PRESENTS AS A VERIFIED ONE.

    Three outcomes exist, not two, and the third is the point: a write we could not
    confirm is NOT a write we know failed -- the device may well have taken it. Calling
    it OK would make an infrastructure failure look like success; calling it REFUSED
    would make it look like the device said no. Both are lies in different directions.
    """
    com, _ = _mgr(monkeypatch=monkeypatch)
    assert _run(com.async_write(_VAC, [27]))["status"] == WRITE_UNCONFIRMED


def test_cow3_a_real_ack_confirms(monkeypatch):
    """[CO-W3] The ack rides the SAME decode line the read uses, so the write
    self-confirms through machinery that already exists."""
    import logging

    com, _ = _mgr(monkeypatch=monkeypatch)

    async def _emit_ack():
        # The device's reply, on the declared source logger.
        logging.getLogger("test.v1").debug("%s['ok']", PREFIX)

    result = _run(com.async_write(_VAC, [27, 25]), after_fire=_emit_ack)
    assert result["status"] == WRITE_OK, result
    assert com.cached(_VAC)["order"] == [27, 25]


@pytest.mark.parametrize("bad, why", [
    ([27, 999], "999 is not a managed room on the active map"),
    ([27, 27], "a duplicate is not an order"),
    ([27, "x"], "a non-int id"),
    ([27, True], "bool is not a room id (isinstance(True, int) is True)"),
])
def test_cow4_an_order_we_cannot_vouch_for_is_refused(monkeypatch, bad, why):
    """[CO-W4] RED IF THE WRITE TRUSTS ITS CALLER.

    Writing an id the user does not manage puts a room into THEIR saved sequence that
    our UI will never show them -- a change to someone else's data that we cannot then
    explain or undo from our own surfaces. Refuse before the wire, not after.
    """
    com, core = _mgr(monkeypatch=monkeypatch)
    assert _run(com.async_write(_VAC, bad))["status"] == WRITE_REFUSED, why
    assert not core.calls, f"a refused order still reached the wire: {core.calls}"


def test_cow5_clear_uses_the_DECLARED_clear_not_a_derived_empty(monkeypatch):
    """[CO-W5] RED IF clear IS DERIVED FROM AN EMPTY payload.

    "The empty case" is a BRAND FACT: an empty list clears Roborock, but another brand
    might need an explicit null, a sentinel, or a different command entirely. Deriving
    it would be core inventing a brand's word -- the exact thing the declaration seam
    exists to prevent.
    """
    cfg = {
        "enabled": True,
        "write": {
            **_WRITE_CFG["write"],
            # A brand whose clear is a DIFFERENT command with a DIFFERENT argument.
            "clear": {"command": "reset_clean_sequence", "params": None},
        },
    }
    com, core = _mgr(cfg=cfg, monkeypatch=monkeypatch)

    _run(com.async_clear(_VAC))

    _, _, data = core.calls[-1]
    assert data["command"] == "reset_clean_sequence", (
        f"clear was derived rather than read from the declaration: {data}"
    )
    assert data["params"] is None


def test_cow6_no_write_declaration_means_no_write(monkeypatch):
    """[CO-W6] RED IF AN UNDECLARED BRAND CAN BE WRITTEN TO.

    The declaration IS the gate. `set_clean_sequence` is the V1 device protocol; a
    Qrevo/B01 model answers a different transport entirely, so its adapter omits the
    write block and must get no write path at all -- not a failing one.
    """
    com, core = _mgr(cfg={"enabled": True, "read": {}}, monkeypatch=monkeypatch)

    assert com.can_write(_VAC) is False
    assert _run(com.async_write(_VAC, [27]))["status"] == WRITE_UNSUPPORTED
    assert _run(com.async_clear(_VAC))["status"] == WRITE_UNSUPPORTED
    assert not core.calls, "an undeclared brand was sent a command"


def test_cow7_provenance_is_recorded_even_when_unconfirmed(monkeypatch):
    """[CO-W7] RED IF AN UNCONFIRMED WRITE IS FORGOTTEN.

    The ack tells us whether we LEARNED that the write landed, not whether it landed.
    Forgetting an unconfirmed write would make a sequence we DID cause look like the
    user's own -- and provenance is exactly what Clear consults before wiping it.
    """
    com, _ = _mgr(monkeypatch=monkeypatch)
    assert com.last_written(_VAC) is None

    assert _run(com.async_write(_VAC, [25, 27]))["status"] == WRITE_UNCONFIRMED
    assert com.last_written(_VAC) == [25, 27]


# --- tiny async runner, so these stay plain unit tests ----------------------

def _run(coro, after_fire=None):
    import asyncio

    async def _go():
        if after_fire is None:
            return await coro
        task = asyncio.ensure_future(coro)
        await asyncio.sleep(0)
        await after_fire()
        return await task

    return asyncio.run(_go())


# ---------------------------------------------------------------------------
# [CO-OV] override switch state — persisted, no-op-safe, does NOT clear on off
# ---------------------------------------------------------------------------

def _mgr_with_data(monkeypatch):
    """A manager that also exposes .data + async_save (persistence spy)."""
    class _CoreWithData(_FakeManager):
        def __init__(self, cfg, known=KNOWN):
            super().__init__(cfg, known)
            self.data = {"vacuums": {}}
            self.saves = 0

        async def async_save(self):
            self.saves += 1

    core = _CoreWithData(_WRITE_CFG, KNOWN)
    com = CleanOrderManager(manager=core)
    monkeypatch.setattr(com, "_config", lambda vacuum_entity_id: _WRITE_CFG)
    return com, core


def test_co_ov1_override_defaults_false(monkeypatch):
    """[CO-OV-1] A vacuum with no stored setting is OFF, not unknown."""
    com, _ = _mgr_with_data(monkeypatch)
    assert com.override_enabled(_VAC) is False


def test_co_ov2_set_override_persists(monkeypatch):
    """[CO-OV-2] set_override_enabled(True) flips the record AND saves.

    Persistence is the whole point -- a user setting must survive a restart, and the
    only way to make it survive is to reach the manager's storage layer. Asserting
    both halves prevents a fix that "works" in memory but drops on reload.
    """
    import asyncio
    com, core = _mgr_with_data(monkeypatch)

    asyncio.run(com.set_override_enabled(_VAC, True))

    assert com.override_enabled(_VAC) is True
    assert core.data["vacuums"][_VAC]["clean_order_override_enabled"] is True
    assert core.saves == 1


def test_co_ov3_setting_the_same_value_does_not_save(monkeypatch):
    """[CO-OV-3] RED IF THE NO-OP PATH WRITES.

    Every entity refresh calls into is_on -> async_write_ha_state; a set-to-current-
    value must not thrash the storage layer, or the flight-recorder chain and the
    room-update dispatch both eat unnecessary disk writes for a control that changed
    nothing.
    """
    import asyncio
    com, core = _mgr_with_data(monkeypatch)
    asyncio.run(com.set_override_enabled(_VAC, False))
    assert core.saves == 0, "an off->off write hit storage"

    asyncio.run(com.set_override_enabled(_VAC, True))
    assert core.saves == 1
    asyncio.run(com.set_override_enabled(_VAC, True))
    assert core.saves == 1, "an on->on write hit storage"


def test_co_ov4_toggling_off_does_NOT_clear_the_device(monkeypatch):
    """[CO-OV-4] RED IF `set_override_enabled(False)` FIRES A DEVICE CALL.

    The whole point of Clear being a separate service is that toggling off must not
    destroy a sequence the user set in their own Roborock app. This is the invariant
    that makes the switch safe to toggle in an automation.
    """
    import asyncio
    com, core = _mgr_with_data(monkeypatch)
    asyncio.run(com.set_override_enabled(_VAC, True))
    core.calls.clear()

    asyncio.run(com.set_override_enabled(_VAC, False))

    assert com.override_enabled(_VAC) is False
    assert not core.calls, f"toggling off fired a device call: {core.calls}"


# ---------------------------------------------------------------------------
# [CO-AP] apply_current_queue — the switch is the gate, empty queue REFUSED
# ---------------------------------------------------------------------------

def _mgr_with_queue(monkeypatch, queue_order):
    """A manager whose _enabled_room_ids_in_order returns `queue_order`."""
    com, core = _mgr_with_data(monkeypatch)
    # Simulate a live active map with these enabled rooms in this order.
    core._enabled_room_ids_in_order = lambda bucket, vac, mid: list(queue_order)
    # get_map_bucket is imported deferred; make it a passthrough for the fake.
    import custom_components.eufy_vacuum.maps.map_manager as mm
    monkeypatch.setattr(mm, "get_map_bucket", lambda **kw: {"rooms": {}})
    return com, core


def test_co_ap1_apply_refuses_when_override_off(monkeypatch):
    """[CO-AP-1] RED IF APPLY CAN FIRE WITHOUT THE SWITCH.

    The switch IS the gate. Without it, a service call from an automation could push a
    sequence with no explicit user intent -- which is the exact promise the switch
    exists to make.
    """
    import asyncio
    com, core = _mgr_with_queue(monkeypatch, [27, 25, 23])

    result = asyncio.run(com.apply_current_queue(_VAC))

    assert result["status"] == WRITE_REFUSED
    assert result.get("reason") == "override_off"
    assert not core.calls, "apply fired with the switch off"


def test_co_ap2_apply_refuses_an_empty_queue(monkeypatch):
    """[CO-AP-2] RED IF APPLY WRITES [] WHEN THE QUEUE IS EMPTY.

    An empty queue is not the same as a clear. Silently writing [] would wipe the
    user's app-set sequence just because they happened to hit Apply with every room
    disabled -- a surprise wipe of somebody else's data. Refuse, so the card can show
    a visible "nothing to apply" state instead.
    """
    import asyncio
    com, core = _mgr_with_queue(monkeypatch, [])
    asyncio.run(com.set_override_enabled(_VAC, True))
    core.calls.clear()

    result = asyncio.run(com.apply_current_queue(_VAC))

    assert result["status"] == WRITE_REFUSED
    assert result.get("reason") == "empty_queue"
    assert not core.calls, f"apply wrote a payload for an empty queue: {core.calls}"


def test_co_ap3_apply_writes_the_current_queue(monkeypatch):
    """[CO-AP-3] Apply is a thin wrapper on async_write that supplies the queue as
    the order. The queue is the intended order, so sequence-to-queue matching is what
    the card's "green" state asserts."""
    import asyncio
    com, core = _mgr_with_queue(monkeypatch, [27, 25, 23])
    asyncio.run(com.set_override_enabled(_VAC, True))
    core.calls.clear()

    result = asyncio.run(com.apply_current_queue(_VAC))

    # No ack was emitted -> unconfirmed, never OK. But the payload did go.
    assert result["status"] == WRITE_UNCONFIRMED, result
    assert result["order"] == [27, 25, 23]
    assert core.calls, "apply did not fire a call"
    _, _, data = core.calls[-1]
    assert data["command"] == "set_clean_sequence"
    assert data["params"] == [27, 25, 23]


# ---------------------------------------------------------------------------
# [CO-N] cache writes NOTIFY — the sensor must not wait for its poll
# ---------------------------------------------------------------------------

def test_co_n1_a_cache_write_fires_update_callbacks(monkeypatch):
    """[CO-N-1] RED IF `_store` STOPS NOTIFYING.

    The sensor is poll-driven, so before this seam existed every read landed in the
    cache and sat there invisible until the platform's next scan — measured at 10s
    and 29s against real hardware. That lag falls exactly on the Apply -> "the row
    turns green" confirmation the UI flow is built around, so the button reads as
    broken for up to half a minute while the device has in fact already acked.

    `_store` is the single funnel for every cache write, which is why the notify
    belongs there: a read path added later inherits it instead of forgetting it.
    """
    com, _ = _mgr_with_data(monkeypatch)
    seen: list[str | None] = []
    com.register_update_callback(lambda *, vacuum_entity_id=None: seen.append(vacuum_entity_id))

    com._store(_VAC, [27, 25], "ok")

    assert seen == [_VAC], "a cache write did not reach the update callbacks"


def test_co_n2_unregister_stops_the_callback(monkeypatch):
    """[CO-N-2] RED IF `unregister_update_callback` DOES NOT DETACH.

    The sensor platform unregisters on unload; a callback that survives holds a
    reference to a removed entity and pushes state writes at it after teardown.
    """
    com, _ = _mgr_with_data(monkeypatch)
    seen: list[str | None] = []

    def _cb(*, vacuum_entity_id=None):
        seen.append(vacuum_entity_id)

    com.register_update_callback(_cb)
    com._store(_VAC, [27], "ok")
    assert seen == [_VAC], "positive control: the callback never fired at all"

    com.unregister_update_callback(_cb)
    com._store(_VAC, [25], "ok")
    assert seen == [_VAC], "unregister left the callback attached"


def test_co_n3_a_raising_callback_cannot_break_the_read(monkeypatch):
    """[CO-N-3] RED IF ONE BAD SUBSCRIBER TAKES DOWN THE CACHE WRITE.

    `_store` runs inside `async_read`, which is documented as never raising into its
    caller. A subscriber that throws must not turn a diagnostic read into an
    exception, and must not stop the SIBLING subscribers from being told.
    """
    com, _ = _mgr_with_data(monkeypatch)
    seen: list[str | None] = []

    def _boom(*, vacuum_entity_id=None):
        raise RuntimeError("subscriber exploded")

    com.register_update_callback(_boom)
    com.register_update_callback(lambda *, vacuum_entity_id=None: seen.append(vacuum_entity_id))

    com._store(_VAC, [27], "ok")  # must not raise

    assert com.cached(_VAC)["status"] == "ok", "the cache write was lost"
    assert seen == [_VAC], "a raising subscriber starved the one after it"


# ---------------------------------------------------------------------------
# [CO-LOCK] the WRITE path must hold the same logger lock the READ path holds
# ---------------------------------------------------------------------------

def test_co_lock1_a_write_overlapping_a_read_restores_the_logger(monkeypatch):
    """[CO-LOCK-1] RED IF `_write_payload` MUTATES THE LOGGER WITHOUT THE LOCK.

    Both paths do the same capture-mutate-restore on a PROCESS-GLOBAL logger:
    remember level + propagate, force DEBUG with propagate=False, attach a handler,
    then restore. The read path has always held `_log_lock` around it. The write path
    took no lock at all, so an overlap interleaves like this:

        read   prior=WARNING          -> sets DEBUG, propagate=False
        write  prior=DEBUG/False      <- captures the READ's temporary values
        read   restores WARNING/True
        write  restores DEBUG/False   <- permanently

    `propagate=False` is the damaging half. The brand's protocol records stop reaching
    Home Assistant's handlers entirely, so the user's log goes quiet for the life of
    the process and nothing raises — the failure is silent by construction.

    Write-vs-write was always reachable: two presses of Apply. Read-vs-write became
    reachable in ba3b3d87, when `async_read` gained its first callers ever and a dock
    arrival started firing reads that can land mid-Apply.

    The assertion is the SYMPTOM — the logger's state afterwards — not "a lock was
    taken". A test that asserted the lock would pass against a lock held over the
    wrong window.
    """
    import asyncio
    import logging

    com, _ = _mgr_with_data(monkeypatch)
    # BOTH halves, or there is no overlap to lose. `_WRITE_CFG` declares no `read`
    # block, so async_read returns at its read_cfg guard without ever touching the
    # logger — the first cut of this test raced a write against nothing and passed
    # against the unlocked code it was written to catch.
    _BOTH_CFG = {
        **_WRITE_CFG,
        "read": {
            "via": "v1_debug_log",
            "command": "get_clean_sequence",
            "service": {"domain": "vacuum", "service": "send_command"},
            "source_logger": "test.v1",
            "decoded_prefix": PREFIX,
        },
    }
    monkeypatch.setattr(com, "_config", lambda vacuum_entity_id: _BOTH_CFG)

    logger = logging.getLogger("test.v1")
    logger.setLevel(logging.WARNING)
    logger.propagate = True
    before = (logger.level, logger.propagate)

    async def _slow_fire(domain, name, vacuum_entity_id, payload=None):
        # Hold the window open long enough for the other coroutine to reach its own
        # capture. Without the lock that is exactly when the values are stolen.
        await asyncio.sleep(0.05)

    monkeypatch.setattr(com, "_fire", _slow_fire)
    monkeypatch.setattr(com, "known_room_ids", lambda vacuum_entity_id: set(KNOWN))

    async def _drive():
        await asyncio.gather(
            com.async_read(_VAC),
            com.async_write(_VAC, [27, 25]),
            return_exceptions=True,
        )

    asyncio.run(asyncio.wait_for(_drive(), timeout=10))

    after = (logger.level, logger.propagate)
    assert after == before, (
        f"the source logger was left at {after} instead of {before} — a write "
        "captured the read's temporary values as its 'prior' and restored those. "
        "propagate=False means the brand's log records never reach Home Assistant "
        "again for the life of the process."
    )


# ---------------------------------------------------------------------------
# [CO-RD] the READ -- every refusal, and the success path no test had taken
#
# `async_read` had tests for what it REFUSES to read and none for a read that
# works: line 336, the `STATUS_OK` store, was never executed. A subsystem whose
# happy path is untested is one where every guard is proven and the thing the
# guards protect is not.
# ---------------------------------------------------------------------------

_READ_CFG = {
    "enabled": True,
    "read": {
        "via": "v1_debug_log",
        "command": "get_clean_sequence",
        "service": {"domain": "vacuum", "service": "send_command"},
        "source_logger": "test.v1.read",
        "decoded_prefix": PREFIX,
    },
}


def _reader(monkeypatch, cfg=None, known=KNOWN):
    """A manager whose `_config` answers `cfg`, defaulting to a full read block."""
    com, core = _mgr(cfg if cfg is not None else _READ_CFG, known, monkeypatch)
    return com, core


def test_co_rd1_no_read_declaration_leaves_the_cache_UNTOUCHED(monkeypatch):
    """[CO-RD-1] A brand with no `read` block is not "unavailable", it is unasked.

    RED IF THE GUARD IS DROPPED: without it `via` becomes "" and the next branch
    stores UNAVAILABLE, which is a CLAIM about the device -- that we looked and got
    nothing. We did not look. The status must stay `never_read`, the distinction the
    whole cache design turns on (see `test_never_read_is_distinct_from_an_empty_order`).

    The service-call assertion is what makes this test discriminate: both paths return
    a cache entry, and only the un-fired command separates "declined to ask" from
    "asked and heard nothing".
    """
    com, core = _reader(monkeypatch, cfg={"enabled": True})

    out = _run(com.async_read(_VAC))

    assert out["status"] == STATUS_NEVER_READ, (
        "a vacuum whose adapter declares no read must stay never_read, not become "
        "unavailable -- unavailable asserts we looked"
    )
    assert out["order"] is None
    assert core.calls == [], "no command may be fired without a read declaration"


def test_co_rd2_an_UNIMPLEMENTED_strategy_is_unavailable_and_fires_NOTHING(monkeypatch):
    """[CO-RD-2] The repoint seam: an unknown `via` fails closed, it does not guess.

    The module docstring names this as the seam for swapping to a proper
    `service_response` once upstream registers the command -- "a DECLARATION change,
    not a code change". An unrecognised declaration must therefore refuse rather than
    fall through to the one strategy that happens to be implemented.

    RED IF THE `via` GUARD IS REMOVED: the status would still read UNAVAILABLE (no
    match arrives either way), so the status alone cannot catch it. `core.calls` can:
    without the guard the command IS fired, against a strategy we do not implement.
    """
    cfg = {"enabled": True, "read": {**_READ_CFG["read"], "via": "service_response"}}
    com, core = _reader(monkeypatch, cfg=cfg)

    out = _run(com.async_read(_VAC))

    assert out["status"] == STATUS_UNAVAILABLE
    assert out["order"] is None
    assert core.calls == [], (
        "an unimplemented strategy fired its command anyway -- the guard is gone and "
        "UNAVAILABLE is hiding it"
    )


def test_co_rd3_a_real_reply_in_the_window_is_cached_as_the_order(monkeypatch):
    """[CO-RD-3] THE SUCCESS PATH, and the live noise it has to survive.

    This is `async_read` working: fire, capture off the DEBUG line, validate the shape,
    cache STATUS_OK. Line 336 -- the only `STATUS_OK` store in the module -- had never
    been executed by any test.

    THE WINDOW IS NOISY BY CONSTRUCTION and the noise is the point. Three lines are
    emitted while the handler is attached, in the order a real device produces them:

      1. a line with no decoded prefix at all (routine library chatter)
      2. the real reply
      3. `[0]` -- the poll tick the module docstring records as arriving every ~15 s

    THE TICK COMES LAST AND THAT ORDERING IS THE WHOLE TEST. The module takes
    `handler.matches[-1]`, so with the tick emitted FIRST this test passed even with
    the predicate deleted: `[0]` was appended, the real order was appended after it,
    and `[-1]` was right either way. The claim was symmetric under its own mutation.
    Emitting the tick after the reply is both the discriminating order and the
    realistic one -- the tick arrives about every 15 s and the window is 3 s long.

    Each line still exercises a different arm of `if result is not None and
    self._predicate(result)`. Drop the predicate half now and the cached order becomes
    `[0]`, which is exactly the production symptom the module docstring describes
    ("the sensor reports `[0]` as an order every ~15 s"), reproduced through the real
    read path rather than against `is_clean_order` in isolation.
    """
    import logging

    com, core = _reader(monkeypatch)
    log = logging.getLogger("test.v1.read")

    async def _fire_and_reply(domain, name, vacuum_entity_id, command=None, payload=None):
        core.calls.append((domain, name, {"entity_id": vacuum_entity_id,
                                          "command": command}))
        log.debug("some unrelated library line")          # parses to None
        log.debug("%s[27, 25, 23]", PREFIX)               # the reply
        log.debug("%s[0]", PREFIX)                        # the tick, AFTER the reply

    monkeypatch.setattr(com, "_fire", _fire_and_reply)

    out = _run(com.async_read(_VAC))

    assert out["status"] == STATUS_OK, "a valid reply did not cache as a reading"
    assert out["order"] == [27, 25, 23], (
        "the cached order is %r -- if it is [0] the handler's predicate stopped "
        "filtering and the poll tick is being read as an order" % (out["order"],)
    )
    assert out["read_at"], "a successful read must stamp read_at"
    assert core.calls, "the read fired no command"


def test_co_rd4_an_INCOMPLETE_read_declaration_fires_nothing(monkeypatch):
    """[CO-RD-4] Half a declaration is not a declaration.

    `_read_via_v1_debug_log` needs all five of source_logger / decoded_prefix /
    service.domain / service.service / command. A block missing one is a half-written
    adapter, and the refusal happens BEFORE the logger is touched and before anything
    is sent.

    RED ON `core.calls` IF THE COMPLETENESS GUARD IS DROPPED: the read would fire with
    `domain=None`, find no match and report UNAVAILABLE -- the same status this test
    sees, which is why the status is not the assertion that matters here.
    """
    cfg = {"enabled": True, "read": dict(_READ_CFG["read"])}
    del cfg["read"]["source_logger"]
    com, core = _reader(monkeypatch, cfg=cfg)

    out = _run(com.async_read(_VAC))

    assert out["status"] == STATUS_UNAVAILABLE
    assert core.calls == [], (
        "an incomplete read declaration still put a command on the wire"
    )


def test_co_rd5_a_torn_room_key_is_stepped_over_not_fatal(monkeypatch):
    """[CO-RD-5] One unreadable room id must not cost the whole vocabulary.

    `known_room_ids` is the read's entire filter vocabulary: if it raises, a diagnostic
    read takes down whatever called it, and if it returns empty the read fails closed
    and the sensor goes unavailable. A single junk key -- a map bucket written by an
    older version, a hand-edited storage file -- must cost exactly that one id.

    RED IF THE `except` IS NARROWED TO TypeError: a non-numeric STRING key raises
    ValueError, which would escape `known_room_ids` into `async_read`, which has no
    handler of its own at that point.
    """
    com, core = _reader(monkeypatch)
    core.get_managed_rooms = lambda *, vacuum_entity_id, map_id: {
        "rooms": {"17": {}, "kitchen": {}, "25": {}, None: {}}
    }

    known = com.known_room_ids(_VAC)

    assert known == {17, 25}, (
        "expected the two readable ids and nothing else, got %r" % (known,)
    )


def test_co_rd6_a_service_that_raises_degrades_to_unavailable(monkeypatch):
    """[CO-RD-6] A missing or unsupported service is a quiet degradation.

    A vacuum whose brand integration is mid-reload, or whose service does not exist at
    all, must yield "no reading" rather than raise into a caller the module docstring
    describes as possibly "mid-dispatch".

    ⚠ TWO HANDLERS STAND BETWEEN THE RAISE AND THE CALLER, and this test proves the
    OUTER one. Narrowing `_fire`'s own `except HomeAssistantError` leaves this test
    GREEN, because `_read_via_v1_debug_log` wraps the entire window in
    `except Exception` -- pragma'd as "defensive", yet load-bearing here -- which
    catches the escapee one frame out and still answers UNAVAILABLE. Measured, not
    assumed: that ablation came back DEAD against this test.

    So the claim here is the DEGRADATION, which is real and bites. `_fire`'s own
    handler is unobservable from the read path; [CO-W-11] is where it can be seen.
    """
    from homeassistant.exceptions import HomeAssistantError

    com, core = _reader(monkeypatch)

    async def _boom(domain, service, data, blocking=False):
        raise HomeAssistantError("service vacuum.send_command not found")

    core.services.async_call = _boom

    out = _run(com.async_read(_VAC))

    assert out["status"] == STATUS_UNAVAILABLE, (
        "a raising service call must degrade to unavailable, not propagate"
    )
    assert out["order"] is None


def test_co_rd7_a_decoded_result_that_is_not_a_list_is_refused():
    """[CO-RD-7] The shape filter's first gate: not a list, not an order.

    Every entry in REAL_DECODED_SHAPES happens to parse to a list, so the
    `isinstance(result, list)` arm was never taken with anything else. These are the
    shapes a different command's reply can take -- a bare dict, a scalar, a string.

    RED IF THAT FIRST `return False` BECOMES `return True`: a status dict would be
    accepted as a clean order.
    """
    for payload in ({"state": 8}, 0, 1, "ok", None, (27, 25)):
        assert is_clean_order(payload, KNOWN) is False, (
            "%r was accepted as a clean order" % (payload,)
        )


# ---------------------------------------------------------------------------
# [CO-N] update callbacks -- the two membership guards
# ---------------------------------------------------------------------------

def test_co_n4_registering_twice_subscribes_once_and_unregistering_a_stranger_is_a_noop(
    monkeypatch,
):
    """[CO-N-4] Both membership guards, each with its own symptom.

    The sensor registers on add and unregisters on remove; HA can run either more than
    once across a reload. The guards make both idempotent.

    TWO CLAIMS, TWO REDS:
      - drop `if callback not in ...` and a double-registered sensor fires TWICE per
        cache write, which is a duplicate state write per read, not a cosmetic issue;
      - drop `if callback in ...` and unregistering a callback that was never
        registered raises ValueError out of HA's `async_will_remove_from_hass`.
    """
    com, _ = _mgr_with_data(monkeypatch)
    fired = []

    def _cb(*, vacuum_entity_id=None):
        fired.append(vacuum_entity_id)

    com.register_update_callback(_cb)
    com.register_update_callback(_cb)          # the second must be ignored

    com._store(_VAC, [27], "ok")
    assert fired == [_VAC], (
        "a double registration fired %d times for one cache write" % len(fired)
    )

    def _other(*, vacuum_entity_id=None):
        pass

    com.unregister_update_callback(_other)     # never registered -- must not raise

    com._store(_VAC, [25], "ok")
    assert fired == [_VAC, _VAC], (
        "unregistering a stranger disturbed the real subscriber"
    )


# ---------------------------------------------------------------------------
# [CO-W] the WRITE -- the three refusals the write path had left untested
# ---------------------------------------------------------------------------

def test_co_w8_an_UNIMPLEMENTED_write_strategy_is_unsupported(monkeypatch):
    """[CO-W-8] The write's repoint seam, same shape as the read's.

    RED IF THE `via` GUARD IS REMOVED: the payload is built and FIRED against a
    strategy we have not implemented, and the caller is told `unconfirmed` -- a word
    that means "it may have landed" about a transport that does not exist.
    """
    cfg = {**_WRITE_CFG, "write": {**_WRITE_CFG["write"], "via": "b01_set_room_order"}}
    com, core = _mgr(cfg, KNOWN, monkeypatch)

    out = _run(com.async_write(_VAC, [27, 25]))

    assert out == {"status": WRITE_UNSUPPORTED, "order": None}
    assert core.calls == [], "an unimplemented write strategy still fired"
    assert com.last_written(_VAC) is None, (
        "provenance was recorded for a write that never happened -- a later Clear "
        "would claim we put that order there"
    )


def test_co_w9_a_write_block_missing_its_service_is_unsupported(monkeypatch):
    """[CO-W-9] A declared write with nowhere to send it.

    `via` is right and the template is present, but `service` names no domain. That is
    an adapter half-written, and the answer is UNSUPPORTED rather than an attempt.

    RED IF THE GUARD DROPS ITS domain/name HALF: `_fire` is called with `domain=None`,
    the fake records a call to nothing, and the result degrades to UNCONFIRMED.
    """
    cfg = {**_WRITE_CFG, "write": {**_WRITE_CFG["write"], "service": {}}}
    com, core = _mgr(cfg, KNOWN, monkeypatch)

    out = _run(com.async_write(_VAC, [27, 25]))

    assert out == {"status": WRITE_UNSUPPORTED, "order": None}
    assert core.calls == []


def test_co_w10_a_write_with_no_ack_DECLARED_fires_and_reports_unconfirmed(monkeypatch):
    """[CO-W-10] No ack machinery declared: fire, record provenance, say unconfirmed.

    Distinct from [CO-W-2], which declares an ack and never hears it. This is the
    adapter declaring no ack AT ALL, and it takes a different early-return path that
    skips the whole capture window.

    THE DISCRIMINATOR IS THE CACHE, not the status -- both paths answer UNCONFIRMED.
    This path does NOT call `_store`, so a previous reading survives the write.

    ⚠ RECORDED, NOT ENDORSED: the acked path's own comment says "the cache now
    describes a device we just changed; the old read is stale" and stores UNAVAILABLE
    for exactly that reason. The same reasoning applies here and this path does not do
    it, so a write through an ack-less declaration leaves a stale order on display.
    This test pins TODAY's behaviour so the divergence cannot change unnoticed; whether
    to converge the two is a behaviour change and so not a test's call.
    """
    cfg = {**_WRITE_CFG, "write": {k: v for k, v in _WRITE_CFG["write"].items()
                                   if k != "ack"}}
    com, core = _mgr(cfg, KNOWN, monkeypatch)
    com._store(_VAC, [1, 2, 3], STATUS_OK)     # a prior reading to notice surviving

    out = _run(com.async_write(_VAC, [27, 25]))

    assert out == {"status": WRITE_UNCONFIRMED, "order": [27, 25]}
    assert com.last_written(_VAC) == [27, 25], (
        "provenance must be recorded even unconfirmed -- the write may well have "
        "landed, and a later Clear needs to know we caused it"
    )
    assert core.calls, "nothing was sent"
    assert com.cached(_VAC)["order"] == [1, 2, 3], (
        "this path wrote the cache; it is the acked path that does so, and the two "
        "being different is what this test exists to pin"
    )


def test_co_ap4_apply_refuses_when_there_is_no_ACTIVE_MAP(monkeypatch):
    """[CO-AP-4] No active map means no queue, and no queue means no write.

    `_current_queue_order` returns `[]` the moment `resolve_active_map_id` answers
    None, which `apply_current_queue` turns into the same visible refusal an empty
    queue gets. The alternative -- carrying on with `map_id=None` -- reaches
    `get_map_bucket` with a bogus key.

    RED IF THE `if not map_id` GUARD IS DROPPED: the fake bucket still yields the
    queue, so Apply WRITES, and a vacuum with no resolved map pushes a sequence to the
    device.
    """
    com, core = _mgr_with_queue(monkeypatch, [27, 25])
    core.resolve_active_map_id = lambda vacuum_entity_id: None
    com._manager.data.setdefault("vacuums", {})[_VAC] = {
        CleanOrderManager.OVERRIDE_ENABLED_KEY: True
    }

    out = _run(com.apply_current_queue(_VAC))

    assert out["status"] == WRITE_REFUSED
    assert out["reason"] == "empty_queue"
    assert core.calls == [], "Apply wrote a sequence with no active map resolved"


def test_co_w11_a_raising_service_on_the_ACK_LESS_write_path_does_not_escape(monkeypatch):
    """[CO-W-11] Where `_fire`'s own HomeAssistantError handler is observable.

    `_fire` swallows `HomeAssistantError` so a missing or mid-reload service degrades
    instead of raising. From the READ path that handler cannot be seen: the caller
    wraps the whole window in `except Exception`, so removing the inner one changes no
    answer ([CO-RD-6] records the measurement).

    THE ACK-LESS WRITE BRANCH IS THE ONE PLACE IT IS LOAD-BEARING. It calls `_fire`
    with no try of its own and then returns, so an escaping error propagates straight
    out of `async_write` into the service call that invoked it -- a user pressing Apply
    on a vacuum whose integration is reloading would get a raised exception rather than
    the honest "unconfirmed".

    RED IF `_fire` STOPS CATCHING IT: this test errors instead of asserting.
    """
    from homeassistant.exceptions import HomeAssistantError

    cfg = {**_WRITE_CFG, "write": {k: v for k, v in _WRITE_CFG["write"].items()
                                   if k != "ack"}}
    com, core = _mgr(cfg, KNOWN, monkeypatch)

    async def _boom(domain, service, data, blocking=False):
        raise HomeAssistantError("integration is reloading")

    core.services.async_call = _boom

    out = _run(com.async_write(_VAC, [27, 25]))

    assert out == {"status": WRITE_UNCONFIRMED, "order": [27, 25]}, (
        "a raising service on the ack-less write path must still report unconfirmed"
    )
    assert com.last_written(_VAC) == [27, 25], (
        "provenance is recorded even when the send raised -- we cannot know it did "
        "not land, and the ack is how we would learn, not whether it happened"
    )
