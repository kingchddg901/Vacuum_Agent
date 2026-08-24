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
