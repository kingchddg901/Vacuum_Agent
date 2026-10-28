"""Every start-protection reason code the backend can emit must have a card key.

The card's refusal path is already right: `state/rooms.js::startBlockedReason` keeps the
machine CODE rather than the English message, `resolveCodedLabel` tries
``rooms.block_reason.<code>``, and the backend's `message` is the last-resort fallback so a
code a card release has never heard of still reads. A5-AG-2 built that.

What nobody checked is whether the keys exist. Before 2.5.3 the family held fourteen
entries — the five card-local codes from `state/rooms.js` and the nine access-graph ones —
and **not one** of the twelve the backend's own start-protection emits. So the resolver ran,
missed, and fell through to English every time. A working resolver over an empty vocabulary
looks exactly like a working resolver.

WHY THE SET IS EXECUTED, NOT LISTED. `build_start_blocker_from_lifecycle` is a pure
function, so [BRK-1] CALLS it once per branch and collects what it actually returns. A
hand-written list of codes is a second copy of the ladder that drifts the moment someone
adds a branch — and the census's own list of this sink's codes was missing ``blocked``,
which is how that failure mode looks in practice. The manager-side codes cannot be executed
without a hass, so [BRK-3] scans the ONE function that emits them, sliced from its own
`def`, rather than the whole module (which carries unrelated `reason` dicts — clean_order's
`override_off`, the access-graph's `no_dock_room`, and more).

Coverage targets
----------------
[BRK-1] every reason `build_start_blocker_from_lifecycle` RETURNS has a key.
[BRK-2] the mutation control: a reason with no key is reported.
[BRK-3] every reason literal in `get_start_status` has a key, including the water pair.
[BRK-4] the in-flight lifecycle states are keyed — they reach the card AS the reason.
[BRK-5] the ladder is exercised: the branches really do produce distinct codes.
"""

from __future__ import annotations

import inspect
import pathlib
import re

from custom_components.eufy_vacuum.core import manager as core_manager
from custom_components.eufy_vacuum.jobs.job_monitor import build_start_blocker_from_lifecycle

REPO = pathlib.Path(__file__).resolve().parents[2]
EN_JS = REPO / "src" / "i18n" / "en.js"
PREFIX = "rooms.block_reason."

#: Everything the ladder needs for a RUNNABLE call. Each branch below overrides only what
#: it needs to trip, so a new required kwarg breaks one place rather than nine.
_RUNNABLE: dict = {
    "lifecycle_state": "ready",
    "lifecycle_message": "",
    "selected_map_id": "m1",
    "active_map_id": "m1",
    "queue_room_ids": [1],
    "payload_room_count": 1,
    "clean_phase_count": 1,
}

#: One override set per branch of build_start_blocker_from_lifecycle, in its own order. The
#: COMMENTS here are documentation; the codes come back from the function.
LADDER_INPUTS: tuple[dict, ...] = (
    {"selected_map_id": ""},                                   # no target map
    {"active_map_id": "m2"},                                   # selected map is not the live one
    {"queue_room_ids": []},                                    # a map, but an empty queue
    {"clean_phase_count": 0},                                  # a queue, but nothing that cleans
    # then one per lifecycle state the ladder branches on, all else runnable
    *({"lifecycle_state": state} for state in
      ("mid_job_service", "active_job_running", "vacuum_busy", "dock_drying", "ready")),
)


def en_keys() -> set[str]:
    """The flat quoted keys defined in en.js.

    Read as text: en.js is a JS module. Its keys are flat quoted strings, so an exact scan
    is possible without parsing JavaScript. Mirrors tests/unit/test_i18n_alias_vocab_keys.py.
    """
    pattern = re.compile(r'^\s*"([a-z0-9_.]+)"\s*:')
    return {
        m.group(1)
        for m in (pattern.match(line) for line in EN_JS.read_text(encoding="utf-8").splitlines())
        if m
    }


def ladder_reasons() -> list[dict]:
    """What the real ladder returns for each branch input."""
    return [build_start_blocker_from_lifecycle(**{**_RUNNABLE, **kwargs}) for kwargs in LADDER_INPUTS]


def unkeyed(codes, keys: set[str]) -> list[str]:
    return sorted({c for c in codes if f"{PREFIX}{c}" not in keys})


def test_brk_1_every_lifecycle_ladder_reason_has_a_key() -> None:
    """[BRK-1]"""
    keys = en_keys()
    assert len(keys) > 2000, f"en.js scan found only {len(keys)} keys — the scanner is broken"

    # `ready` is not a refusal and never reaches the resolver; everything else does, including
    # dock_drying, which arrives on the WARNING path rather than the blocked one.
    codes = [r["reason"] for r in ladder_reasons() if r["reason"] != "ready"]
    missing = unkeyed(codes, keys)
    assert not missing, (
        "the start-blocker ladder emits these and the card has no key, so the refusal reaches "
        "the user as the backend's English sentence:\n  "
        + "\n  ".join(f"{PREFIX}{c}" for c in missing)
    )


def test_brk_2_a_reason_with_no_key_is_reported() -> None:
    """[BRK-2] the mutation control — [BRK-1] passing must mean something."""
    keys = en_keys()
    injected = [r["reason"] for r in ladder_reasons() if r["reason"] != "ready"]
    injected.append("coffee_break")
    assert unkeyed(injected, keys) == ["coffee_break"]
    # And the real set is still clean, so the injection is what produced that one hit.
    assert not unkeyed([c for c in injected if c != "coffee_break"], keys)


def test_brk_3_every_get_start_status_reason_has_a_key() -> None:
    """[BRK-3]"""
    keys = en_keys()
    source = inspect.getsource(core_manager.EufyVacuumManager.get_start_status)
    # Both shapes the function uses: the payload key, and the water pre-check's local.
    codes = set(re.findall(r'"reason":\s*"([a-z_]+)"', source))
    codes |= set(re.findall(r'water_reason\s*=\s*"([a-z_]+)"', source))
    # `preflight.get("reason", "blocked")` — the literal default, which is a code in its own
    # right and the one the census's list of this sink missed.
    codes |= set(re.findall(r'\.get\("reason",\s*"([a-z_]+)"\)', source))

    assert len(codes) >= 5, (
        f"only {len(codes)} reason literal(s) found in get_start_status — the slice or the "
        "patterns are wrong, and an empty scan passes everything"
    )
    missing = unkeyed(codes, keys)
    assert not missing, (
        "get_start_status emits these with no card key:\n  "
        + "\n  ".join(f"{PREFIX}{c}" for c in missing)
    )


def test_brk_4_inflight_lifecycle_states_are_keyed() -> None:
    """[BRK-4] these reach the card AS the reason, not as a lifecycle label."""
    keys = en_keys()
    states = set(core_manager._INFLIGHT_LIFECYCLE_STATES)
    assert states, "the in-flight set is empty — this gate would pass vacuously"
    missing = unkeyed(states, keys)
    assert not missing, (
        "`_job_in_flight_reason` forwards the lifecycle STATE as the reason code, so each "
        "needs a block_reason sentence of its own — a vocab.lifecycle_state word is the "
        "wrong register for a refusal:\n  " + "\n  ".join(f"{PREFIX}{c}" for c in missing)
    )


def test_brk_5_the_ladder_branches_are_actually_distinct() -> None:
    """[BRK-5] a gate over a ladder that always answers the same thing proves nothing."""
    reasons = [r["reason"] for r in ladder_reasons()]
    assert len(set(reasons)) == len(LADDER_INPUTS), (
        "two branch inputs produced the same reason, so at least one branch is unexercised: "
        f"{reasons}"
    )
    # The blocked/warning split is part of the contract: dock_drying is a warning and `ready`
    # is neither, and the card renders those differently.
    by_reason = {r["reason"]: r for r in ladder_reasons()}
    assert by_reason["dock_drying"]["blocked"] is False
    assert by_reason["dock_drying"].get("warning") is True
    assert by_reason["ready"]["blocked"] is False
    assert by_reason["vacuum_busy"]["blocked"] is True
