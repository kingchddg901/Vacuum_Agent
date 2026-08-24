"""Semantic receipts — radio-discipline logging for the stall-capture pilot.

DESIGN: `.claude/notes/synthesis/PROTOCOL-semantic-flight-recorder.md`, items 6 (this pilot),
7 (why the causal chain is the real cost) and 8 (the message protocol). Read item 8 before
changing anything here; the ordering and the vocabularies are the design, not conventions.

THE MESSAGE. A receipt is a radio transmission, addressee first:

    TO | this is | FROM | outcome | facts... | [provenance]

Addressee first because every station decides on the first token whether to keep listening,
and because it states the OBLIGATION before the content. The reply names the caller back, so
an edge is asserted by two parties: a pass-through that CLAIMS it called X is contradicted by
X naming whoever really called it, rather than by someone's reading of the code.

MESSAGES DO NOT NEST. No receipt carries its ancestry. Each names only its immediate
neighbours; the chain is a replay-time join on correlation + TO/FROM. That is what keeps a
receipt constant-size at any depth — if messages nested, the deepest paths would cost the
most, which is backwards. PROVENANCE OBEYS THE SAME RULE: it marks the INJECTION POINT only
and is never inherited forward, because inheriting a marker IS ancestry in the message. A
reader learns a chain began synthetically by joining at replay, like anything else structural.

COST. `emit()` checks the log level BEFORE it touches anything else, and facts are passed as
positional values that are already locals at the call site — never a dict comprehension, never
a call. The pilot's cost gate proves the property structurally rather than by benchmark:
unarmed, a sentinel's `__len__`/`__repr__` is never reached. See
`reference_blocking_io_test_guard` for why a benchmark would be worthless here — a perf guard
that cannot fail is false confidence, and this repo already shipped one.
"""
from __future__ import annotations

import logging
from typing import Any

#: A CHILD of the package logger `debug_capture` arms. Its own level stays NOTSET, so
#: `isEnabledFor` resolves against the parent's effective level — arming the package arms
#: receipts, and nothing else has to know they exist. Records propagate UP to the parent's
#: ring handler and stop there, because the parent is the one carrying propagate=False.
_LOGGER = logging.getLogger("custom_components.eufy_vacuum.receipts")

#: The wire prefix. The decoder keys on this; nothing else in the package emits it.
WIRE = "RCPT"

# ---------------------------------------------------------------------------
# Closed vocabularies. Free text here is prose returning by the back door, which is
# the one thing the whole design exists to prevent — so these are tuples.
#
# ⚠ WHAT THE GATE ENFORCES IS NARROWER THAN THIS HEADING SAID. This block ended
# "and the gate rejects anything outside them" until 2026-08-24 (ledger D6). That
# holds for three of the five vocabularies below and is FALSE for two of them.
# `scripts/check_receipts.py` reads `emit()` call sites with AST, so it can only
# police a value it can name at a fixed argument position:
#   STATIONS        ENFORCED — both `to` and `frm` are checked for membership, and
#                   `frm` must additionally equal the emitting file's own module path.
#   OUTCOMES        ENFORCED via the catalog — each entry's declared `outcomes` are
#                   checked against OUTCOMES, and each emitted outcome against the
#                   entry. A dead declared outcome is reported too.
#   PROVENANCE      ENFORCED only when `prov=` is a literal keyword argument; a
#                   computed value is not seen at all.
#   DECLINE_REASONS NOT ENFORCED. Both ride as positional *facts*, and the gate
#   READABILITY     captures facts only as a COUNT (`max(0, len(args) - 4)`), so
#                   their values never reach it. A misspelled decline reason passes,
#                   and a declared-but-never-emitted member is invisible — `no_map`
#                   below is exactly that today. Fixing it is a change to the GATE,
#                   not to these tuples; tracked as ledger C6, still open.
# ---------------------------------------------------------------------------

#: What happened at this station.
#:   C  called    — I transmitted to a target and a reply is OBLIGED
#:   B  broadcast — I transmitted to all stations; a reply is NOT obliged
#:   R  reply     — I am answering a call, naming my caller
#:   P  pass      — I did the thing
#:   D  declined  — I HEARD and deliberately did not act. See DECLINE_REASONS.
#:   F  fail      — I tried and could not
#: D is the one §4 never stated. §4 says success may not be silent; a legitimate
#: DECLINE may not be silent either, and it is by far the commonest reason a
#: checkpoint is missing. P removes "ran silently", D removes "legitimately
#: bypassed", and what is left absent is then worth investigating.
OUTCOMES: tuple[str, ...] = ("C", "B", "R", "P", "D", "F")

#: Why a station heard the call and did not act. Closed, and owned by the consumer
#: because it is the only party that knows why.
DECLINE_REASONS: tuple[str, ...] = (
    "not_armed",        # the per-vacuum switch is off — a deliberate configuration
    "no_room",          # the run has no resolved current room to render
    "no_map",           # no active map id
    "no_render_data",   # the map source produced nothing decodable
    "unusable",         # render data present but the room has no cells
    "no_pillow",        # the optional CV stack is absent
    "no_runtime",       # the integration's runtime is not loaded — heard, nothing to act with
)

#: How well the receiver read what it got — the "I read you Lima Charlie" report. This is
#: NOT an acknowledgement; it is a QUALITY CLAIM by the receiver, and it is the four-state
#: distinction this codebase keeps rediscovering the hard way: the diagnostics dump where
#: "we couldn't find it" and "your vacuum doesn't have it" were byte-identical; absent vs
#: declared-empty in adapter catalogs; held/stale map data served to consumers that acted on
#: it; `not_configured` meaning both "no pose declared" and "no position exists". The fourth
#: state is no reply at all, which is why this vocabulary has three members and not four.
READABILITY: tuple[str, ...] = (
    "lc",      # loud and clear — complete, fresh, as expected
    "weak",    # received and usable, but degraded: stale, partial, or defaulted
    "broken",  # received and NOT usable
)

#: THE STATIONS. Closed, like every other vocabulary here — free text would let a typo mint
#: a new station silently, which is the layer-3 version of the drift this whole design exists
#: to stop.
#:
#: THREE LAYERS, AND THEY MUST AGREE: file, variable, station. They are separate naming
#: systems and nothing forces them to line up — which is exactly how four measurements of the
#: subsystem->core seam produced three different answers on 2026-08-09. Ten subsystems define
#: a `manager.py`, every call site binds it to a name spelled `manager`, and both the core
#: façade and the subsystem implementation define `set_active_theme`. A static read cannot
#: tell those apart and fails SILENTLY, with a confident number.
#:
#: So a station MIRRORS ITS MODULE PATH, and the gate checks that — a copy-pasted receipt
#: that kept the wrong station is caught mechanically, which is a check that only exists
#: because the layers agree. Arbitrary names would leave nothing verifiable but membership.
#:
#: DECLARED, NEVER DERIVED from `__name__`. Deriving would make a file move silently change a
#: station identity, and §18 says a semantic id never silently changes meaning. Declared +
#: aligned means a move FORCES the choice — keep the station and accept a flagged mismatch,
#: or rename it and knowingly break historical decode. Either way it surfaces.
#:
#: ⚠ THREE OF THESE ARE DECLARED AND SILENT, AND ONE OF THEM CANNOT SPEAK AT ALL
#: (ledger C8, verified 2026-08-24). Only `listeners.stall_capture` and
#: `services.stall_capture` ever appear as `frm` in the package; `mapping.map_source`
#: is only ever addressed. `core`, `pose_store` and `mapping.stall_capture_render`
#: appear in no `emit()` call at all — and `scripts/check_receipts.py` has NO
#: dead-station check. It reports a declared-but-unemitted CATALOG key and a
#: declared-but-unemitted OUTCOME; a station nobody uses passes silently.
#:
#: `core` is worse than silent, it is UNSPEAKABLE. The alignment rule above is checked
#: against the emitting FILE's path, and the hub is `core/manager.py`, which derives
#: `core.manager` — so the first receipt the hub ever sends as `"core"` is REFUSED
#: ("a station may only transmit as itself"). Nothing is broken today because nothing
#: emits; the choice (rename the station to `core.manager`, or leave the hub
#: uninstrumented) is forced the moment somebody adds a receipt there. The other two
#: silent stations are aligned and merely uninstrumented: `pose_store.py` and
#: `mapping/stall_capture_render.py` would each derive their declared name correctly.
STATIONS: tuple[str, ...] = (
    "ANY",                      # all stations this net — a broadcast, obliging nobody
    "core",                     # core/manager.py, the hub — unspeakable, see the ⚠ above
    "listeners.stall_capture",  # the consumer
    "services.stall_capture",   # the maintainer injector
    "mapping.map_source",       # the pose/render provider
    "pose_store",               # the ring
    "mapping.stall_capture_render",
)

#: NEVER BRANCH ON THIS. `dev_inject_stall` exists so every downstream consumer runs for
#: real; gating on the caller would build an injector that exercises a path the real event
#: never takes. Record it; do not read it.
PROVENANCE: tuple[str, ...] = ("live", "synth", "replay")

#: PROVENANCE IS A PROPERTY OF THE RECEIPT, NOT OF A CONTEXT.
#:
#: An earlier build rode this on a ContextVar and INHERITED it into everything a call caused,
#: so a capture triggered by the injector reported `live+synth`. That was wrong twice over.
#:
#: It is wrong on the facts: the capture genuinely executed. It really read the map, really
#: rendered, really wrote the file. Its work is live. What was synthetic is the STIMULUS, and
#: that is a fact about the injection point, not about everything downstream of it.
#:
#: And it is wrong on the protocol: inheriting a marker forward is ANCESTRY CARRIED IN THE
#: MESSAGE, which is precisely what item 8's rule 5 forbids — messages do not nest. A reader
#: learns the chain began synthetically by JOINING at replay, the same way they learn
#: anything else structural. Stamping every link is the accumulation the design refuses.
#:
#: Practical dividend: §11's executor boundary stops mattering here. Nothing has to cross it,
#: so nothing can silently fail to.
DEFAULT_PROVENANCE = "live"


def armed() -> bool:
    """Is anything capturing? A bare level check — the whole cost when unarmed."""
    return _LOGGER.isEnabledFor(logging.DEBUG)


def emit(msg: str, to: str, frm: str, outcome: str, *facts: Any,
         prov: str = DEFAULT_PROVENANCE) -> None:
    """Transmit one receipt.

    THREE IDENTITIES, not two — "Chafee this is Nimitz: <message>". ``to`` and ``frm`` are
    STATIONS; ``msg`` is the catalog key naming what is being said. Collapsing the message
    into the sender is a mistake that reads fine until two different messages leave the same
    station, which is most of them.

    ARGUMENT ORDER IS KEY-FIRST, WIRE ORDER IS ADDRESSEE-FIRST, deliberately. The gate scans
    source for a literal first argument, and a reader of the code wants the message name
    first; a reader of the DUMP wants the addressee first, so every line can be dismissed or
    kept on its first token. Both are cheap, so both get what they need.

    ``facts`` are positional and must already be locals at the call site — the catalog
    declares their names, types and units, so the wire carries values only. A dict or a
    comprehension here defeats the cost property the gate pins.

    Never raises. A recorder that can break the operation it observes is worse than no
    recorder, and an unknown vocabulary value is recorded AS-IS rather than dropped: losing
    evidence to a validation error is the wrong trade at runtime. The GATE is where
    vocabulary violations are caught — at author time, where they are cheap.
    """
    if not _LOGGER.isEnabledFor(logging.DEBUG):
        return
    try:
        body = " ".join(_escape(f) for f in facts)
        _LOGGER.debug("%s|%s|%s|%s|%s|%s|%s", WIRE, to, frm, msg, outcome, body, prov)
    except Exception:  # noqa: BLE001 - never let instrumentation break the caller
        pass


def _escape(value: Any) -> str:
    """Make one fact safe for a space-separated, pipe-delimited line.

    FOUND BY THE PILOT, first run. `map_id` is a NAME on Roborock — "Main floor" — and the
    space split it into two facts, so the decoder read `map=Main room=floor` and reported an
    arity mismatch. The catalog had already declared this field as brand-variant; the WIRE
    had not been told. That is the same defect class as every headline repair in 2.0.0: a
    field whose declared type and whose transport disagree.

    Percent-encoding, not quoting: quoting needs a parser and a parser needs an escape for
    the quote. Three characters is the whole grammar, and `unescape` is its exact inverse —
    which the round-trip test pins, because an encoder without a proven inverse is just a
    different way to lose the value.
    """
    return (str(value).replace("%", "%25").replace("|", "%7C").replace(" ", "%20")) or "%E"


def unescape(token: str) -> str:
    """Inverse of :func:`_escape`. Order matters: %25 last, or it eats the others."""
    if token == "%E":
        return ""
    return token.replace("%20", " ").replace("%7C", "|").replace("%25", "%")
