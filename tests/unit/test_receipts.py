"""receipts/ — the vocabulary, the cost property, the ladder, and provenance.

Design: `.claude/notes/synthesis/PROTOCOL-semantic-flight-recorder.md` items 6 and 8.

Coverage targets
----------------
[RC-1]  unarmed, NO fact is computed — the cost property, asserted structurally.
[RC-2]  armed, the receipt reaches the ring in radio order (addressee first).
[RC-3]  provenance is stated (`live`), never assumed.
[RC-4]  provenance STACKS and is inherited by caused work.
[RC-5]  the §9 ladder: locale -> base language -> English -> raw evidence.
[RC-6]  an unknown id stays inspectable rather than crashing the decoder.
[RC-8]  a fact survives the wire — spaces, pipes, percents (found by the pilot, run 1).
[RC-9]  the executor boundary is a NON-issue now that nothing propagates.
[RC-7]  emit never raises, whatever it is handed.
"""
from __future__ import annotations

import logging

import pytest

from custom_components.eufy_vacuum import receipts


class _Sentinel:
    """A fact that RECORDS being looked at.

    The cost property is not "is it fast" — a benchmark in a Docker test container is noisy,
    gets loosened the first time CI flakes, and lands back at always-green, which is exactly
    what `reference_blocking_io_test_guard` documents happening here before. It is "is any
    work done", which is deterministic and immune to load.
    """

    def __init__(self) -> None:
        self.reads = 0

    def __str__(self) -> str:
        self.reads += 1
        return "looked"

    __repr__ = __str__


@pytest.fixture
def ring():
    """Arm a handler on the package logger the way debug_capture does."""
    logger = logging.getLogger("custom_components.eufy_vacuum")
    records: list[str] = []

    class _H(logging.Handler):
        def emit(self, record):  # noqa: D102
            records.append(record.getMessage())

    h = _H()
    prior_level, prior_prop = logger.level, logger.propagate
    logger.setLevel(logging.DEBUG)
    logger.propagate = False
    logger.addHandler(h)
    try:
        yield records
    finally:
        logger.removeHandler(h)
        logger.setLevel(prior_level)
        logger.propagate = prior_prop


def test_rc1_unarmed_computes_no_fact():
    """[RC-1] THE cost gate. Unarmed, the level check returns before anything is touched.

    Ablate it by moving the isEnabledFor check below the body build in `emit`, and this
    goes red — which is the only reason to trust it.
    """
    logger = logging.getLogger("custom_components.eufy_vacuum")
    prior = logger.level
    logger.setLevel(logging.WARNING)  # unarmed
    s = _Sentinel()
    try:
        for _ in range(1000):
            receipts.emit("stall.capture.heard", "a", "b", "R", s, s, s)
    finally:
        logger.setLevel(prior)

    assert s.reads == 0, "a fact was rendered while nothing was capturing"


def test_rc2_armed_writes_the_wire_in_radio_order(ring):
    """[RC-2] Addressee first on the wire — every station decides on the first token."""
    receipts.emit("stall.capture.heard", "stall.detector", "stall.capture", "R",
                  "vacuum.ivy", "Main floor", 27)

    assert len(ring) == 1
    parts = ring[0].split("|")
    assert parts[0] == receipts.WIRE
    assert parts[1] == "stall.detector", "addressee must come first"
    assert parts[2] == "stall.capture"
    assert parts[3] == "stall.capture.heard"
    assert parts[4] == "R"


def test_rc3_live_is_the_default_and_true(ring):
    """[RC-3] Every station truthfully reports `live`, because it truthfully is."""
    receipts.emit("stall.capture.heard", "a", "b", "R", "v", "m", 1)

    assert ring[0].split("|")[-1] == "live"


def test_rc4_provenance_marks_the_injection_point_only(ring):
    """[RC-4] It is NOT inherited, and the reason is the protocol, not convenience.

    An earlier build rode this on a ContextVar and stamped `live+synth` onto everything the
    injector caused. Wrong on the facts — the capture really did read the map, render and
    write, so its work IS live; what was synthetic is the STIMULUS. And wrong on the
    protocol: carrying a marker forward is ANCESTRY IN THE MESSAGE, which item 8 rule 5
    forbids. A reader learns the chain began synthetically by JOINING at replay.

    The dividend is that §11's executor boundary stops mattering — nothing has to cross it,
    so nothing can silently fail to. See [RC-9].
    """
    receipts.emit("stall.inject.fired", "ANY", "services.stall_capture", "B",
                  "v", "m", 1, prov="synth")
    receipts.emit("stall.capture.heard", "a", "b", "R", "v", "m", 1)

    assert ring[0].split("|")[-1] == "synth", "the injection point marks itself"
    assert ring[1].split("|")[-1] == "live", "and nothing downstream inherits it"


def test_rc4b_a_bad_provenance_is_recorded_not_dropped(ring):
    """[RC-4b] The vocabulary is closed, but it is enforced by the GATE, not at runtime.

    `emit` records an odd value rather than refusing it. Losing evidence to a validation
    error in the middle of an incident is the wrong trade — and author time is where the
    violation is cheap, which is why `check_receipts.py` fails on a prov outside PROVENANCE.
    """
    receipts.emit("stall.capture.heard", "a", "b", "R", "v", "m", 1, prov="probably_real")

    assert ring[0].split("|")[-1] == "probably_real", "evidence survives; the gate judges"
    assert "probably_real" not in receipts.PROVENANCE


@pytest.mark.parametrize("value", [
    "Main floor",        # THE case that found this: a Roborock map_id is a NAME
    "a|b",               # the field delimiter
    "100%",              # the escape character itself
    "% %20 %7C",         # already-encoded-looking input must survive verbatim
    "",                  # empty is a value, not an absent field
    "Heidi & Chris",     # a real room name, spaces and an ampersand
    "27",
])
def test_rc8_facts_round_trip_through_the_wire(ring, value):
    """[RC-8] The encoder must have a proven inverse.

    FOUND BY THE PILOT ON ITS FIRST RUN — not by review. `map_id` is "Main floor" on
    Roborock; the space split it into two facts and the decoder rendered
    `map=Main room=floor`. The catalog had declared the field brand-variant; the WIRE had
    not been told. Same defect class as every headline repair in 2.0.0: a field whose
    declared type and whose transport disagree.

    `%25` must unescape LAST or it eats the others — ablate by reordering `unescape` and
    the `"% %20 %7C"` case goes red.
    """
    receipts.emit("stall.capture.written", "a", "b", "P", value, "path")

    body = ring[0].split("|")[5]
    tokens = body.split()
    assert len(tokens) == 2, f"a fact with a space or pipe broke the field count: {body!r}"
    assert receipts.unescape(tokens[0]) == value


def test_rc7_emit_never_raises(ring):
    """[RC-7] A recorder that can break the operation it observes is worse than none."""
    class _Hostile:
        def __str__(self):
            raise RuntimeError("boom")

    receipts.emit("stall.capture.heard", "a", "b", "R", _Hostile(), "m", 1)  # must not raise


async def test_rc9_the_executor_boundary_no_longer_matters(ring):
    """[RC-9] §11 flags that a ContextVar does not cross into a thread pool. Measured here
    on 2026-08-09, an inherited marker was silently replaced by the DEFAULT across that
    boundary — a synthetic run's render, trail read and atomic write all claimed to be real.

    Not inheriting removes the hazard rather than working around it: a receipt from an
    executor says `live`, which is true, because that thread really did the work. This test
    exists to pin that the boundary is a NON-issue now, so nobody reintroduces propagation
    without rediscovering why it was removed.
    """
    import asyncio

    def _in_thread():
        receipts.emit("stall.capture.written", "ANY", "listeners.stall_capture", "P", "v", "p")

    receipts.emit("stall.capture.written", "ANY", "listeners.stall_capture", "P", "v", "p")
    await asyncio.get_running_loop().run_in_executor(None, _in_thread)

    assert [x.split("|")[-1] for x in ring] == ["live", "live"]


# ---------------------------------------------------------------------------
# The decoder. These two were listed as coverage targets from the first commit and were
# not written for several hours — the file's own docstring claimed tests that did not
# exist, which is the same dead-declaration rot the gate now checks for in the catalog.
# ---------------------------------------------------------------------------

def _dec():
    import sys
    from pathlib import Path as _P
    sys.path.insert(0, str(_P(__file__).resolve().parents[2] / "scripts"))
    import decode_receipts
    return decode_receipts


def test_rc5_the_fallback_ladder_never_destroys_evidence(monkeypatch):
    """[RC-5] §9's ladder, every rung: locale -> base language -> English -> RAW.

    "A broken localization system must never destroy the evidence" — so the bottom rung is
    always readable. The card already runs this exact ladder and `check:i18n` Part A tests
    it; this is the same shape against a different catalog, and it is tested here because a
    ladder only exercised once it HAS rungs is a ladder nobody has tested.
    """
    dec = _dec()
    rec = {"msg": "stall.capture.declined", "outcome": "D",
           "facts": ["vacuum.ivy", "not_armed"], "prov": ["live"], "line": ""}

    monkeypatch.setattr(dec, "LOCALES", {
        "pt-BR": {"stall.capture.declined": "PT-BR {vacuum}: {reason}"},
        "pt": {"stall.capture.declined": "PT {vacuum}: {reason}"},
    })

    assert dec.render_prose(rec, "pt-BR").startswith("PT-BR")      # rung 1: exact locale
    assert dec.render_prose(rec, "pt-PT").startswith("PT ")        # rung 2: base language
    assert "told not to answer" in dec.render_prose(rec, "de")     # rung 3: English
    assert "not_armed" in dec.render_prose(rec, None)

    # rung 4: prose that does not fit its own facts still yields the evidence
    monkeypatch.setattr(dec, "LOCALES", {"xx": {"stall.capture.declined": "{nope}"}})
    out = dec.render_prose(rec, "xx")
    assert "vacuum.ivy" in out and "not_armed" in out, out


def test_rc6_an_unknown_id_stays_inspectable():
    """[RC-6] A decoder that crashed on a key it had not seen would destroy the trace of
    exactly the change that introduced it — the moment you most need to read it."""
    dec = _dec()
    rec = {"msg": "stall.capture.invented_tomorrow", "outcome": "P",
           "facts": ["vacuum.ivy", "42"], "prov": ["live"], "line": ""}

    out = dec.render_prose(rec, None)

    assert "unknown id" in out
    assert "vacuum.ivy" in out and "42" in out, "raw facts must survive an unknown key"
