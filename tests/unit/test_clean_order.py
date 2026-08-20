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
    STATUS_NEVER_READ,
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
