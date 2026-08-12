"""The semantic catalog for the stall-capture pilot.

ONE catalog, two renders. The raw wire view and the human prose view are both projections of
these entries — nothing is maintained twice, because two documents drift and the drift is
one-way and silent. This mirrors `src/i18n/en.js`, which the card already treats the same
way: one source, and `check:i18n` fails FATALLY on a key used but not defined.

WHAT IS AND IS NOT HERE. Entries carry MEANING, FIELDS and PROSE. They do NOT carry the
contract — "what this station is supposed to do" lives in the DR docs (§16: DR says how the
system is supposed to work, the recorder says what this execution actually did), and copying
it here would create exactly the second document that drifts. `dr` is a POINTER, not a copy.

FIELD SHAPE IS `(name, type, unit)` AND ALL THREE ARE REQUIRED. Not the "can also declare" of
§6. Prose is rewritable — §3 keeps the key stable so wording can change without invalidating
history — but a wrong TYPE or UNIT corrupts every receipt that ever carried it and cannot be
fixed after the fact. This project's headline repairs are all undeclared field semantics:

    cleaning_area   Eufy ft^2 vs Roborock m^2, unit undeclared at the boundary
    clean_mode      display label vs canonical token, one name, two vocabularies
    path_type       the literal string "None" riding the wire
    code            int|None, conflating "no code" with "field absent"

It is also what makes the neighbour-diff honest: comparing adjacent receipts detects a
transformation only if both ends record the field the same way. `unit=None` is a legitimate
value meaning dimensionless — but it must be STATED, for the same reason provenance states
`live` rather than assuming it.
"""
from __future__ import annotations

from typing import Any

#: Field types the gate understands. `enum:X` resolves against the vocabulary named X.
TYPES: tuple[str, ...] = (
    "entity_id",
    "map_id",           # STR canonical. Roborock's is a NAME, Eufy's a number — the
                        # canonical form on the wire is the string, and this declaration
                        # is the only thing that stops a decoder assuming otherwise.
    "room_id",
    "int",
    "path",
    "enum:decline_reason",
    "enum:readability",
)

CATALOG: dict[str, dict[str, Any]] = {
    # -- the injector ------------------------------------------------------------------
    "stall.inject.fired": {
        "meaning": "a synthetic stall was transmitted on the net",
        "outcomes": ("B",),
        "fields": (("vacuum", "entity_id", None),
                   ("map", "map_id", None),
                   ("room", "room_id", None)),
        "en": "Injected a synthetic stall for {vacuum} on map {map}, room {room}.",
        "dr": "02 §services / 04 §6a",
    },

    # -- the consumer, heard/declined --------------------------------------------------
    "stall.capture.heard": {
        "meaning": "the stall-capture consumer received the event and will act",
        "outcomes": ("R",),
        "fields": (("vacuum", "entity_id", None),
                   ("map", "map_id", None),
                   ("room", "room_id", None)),
        "en": "Stall capture heard the call for {vacuum}, map {map}, room {room}.",
        "dr": "04 §6a",
    },
    "stall.capture.declined": {
        "meaning": "the consumer heard the call and deliberately did not write an artifact",
        "outcomes": ("D",),
        "fields": (("vacuum", "entity_id", None),
                   ("reason", "enum:decline_reason", None)),
        # The sentence the whole pilot exists to make the dump able to say. On 2026-08-09 a
        # real "no image generated" cost four queries and a .storage read to answer, and the
        # answer was not_armed — one of ten SILENT returns in a consumer with thirteen exits.
        "en": "Stall capture heard the call for {vacuum} and was told not to answer: {reason}.",
        "dr": "04 §6a",
    },

    # -- the pose call: a DIRECTED call, and its reply carries a quality report ---------
    "stall.capture.pose.called": {
        "meaning": "the consumer asked the map subsystem for the robot's live position",
        "outcomes": ("C",),
        "fields": (("vacuum", "entity_id", None),),
        "en": "Asked the map source for {vacuum}'s live pose.",
        "dr": "31 §live pose",
    },
    "stall.capture.pose.observed": {
        "meaning": "the capture observed what came back from the pose call",
        "outcomes": ("P",),
        "fields": (("vacuum", "entity_id", None),
                   ("read", "enum:readability", None)),
        # `weak` is the case that matters: an answer arrived carrying no position, or a
        # held/stale source. That used to be indistinguishable from a clean read, which is
        # how a brand shipped with no dot for months and nobody noticed.
        # OBSERVED, not "replied". An earlier draft emitted this as `FROM=map.source`, which
        # was the capture putting words in an uninstrumented station's mouth — §20's confident
        # liar, and it made the pilot look two-party when only ONE station emits. A real
        # two-party edge needs map.source to speak for itself; that is chain-pilot work. Until
        # then this is honestly the capture's own observation.
        "en": "The capture read {vacuum}'s pose as {read}.",
        "dr": "31 §live pose",
    },
    "stall.capture.trail.read": {
        "meaning": "the capture observed what the pose ring held for the stall window",
        "outcomes": ("P",),
        "fields": (("vacuum", "entity_id", None),
                   ("points", "int", "count"),
                   ("window", "int", "seconds")),
        # Distinct points, not rows: a stationary robot yields many rows and one place, and
        # the renderer's threshold is about places. `window` is derived from the brand's
        # declared pose cadence, so a Roborock's +/-75s and a Eufy's +/-30s are both visible
        # in the dump rather than being a constant somebody has to look up.
        "en": "The capture read {points} trail point(s) for {vacuum} over a ±{window}s window.",
        "dr": "04 §6a",
    },

    # -- the work ----------------------------------------------------------------------
    "stall.capture.rendered": {
        "meaning": "a PNG was produced for the room the robot stopped in",
        # P only. A render that returns None is a DECLINE with a reason (no_pillow /
        # unusable), and a render that raises is caught by the handler, so there is no path
        # on which this station reports F. Declaring one would assert a capability that
        # does not exist — the same dead-declaration rot the gate checks for keys.
        "outcomes": ("P",),
        "fields": (("vacuum", "entity_id", None),
                   ("room", "room_id", None),
                   ("bytes", "int", "bytes")),
        "en": "Rendered {bytes} bytes for {vacuum}, room {room}.",
        "dr": "04 §6a",
    },
    "stall.capture.written": {
        "meaning": "the PNG was written atomically to its stable path",
        "outcomes": ("P", "F"),
        "fields": (("vacuum", "entity_id", None), ("path", "path", None)),
        # One file per (vacuum, map), OVERWRITTEN — deliberate, and DR says so. The receipt
        # is what makes the overwrite auditable: with provenance on the wire, a capture
        # replaced by a synthetic one is visible in the log even though the file is not.
        # See docs/dev/deltas `live:STALL-PROV-1`.
        "en": "Wrote the capture for {vacuum} to {path}.",
        "dr": "04 §6a",
    },
    "stall.capture.announced": {
        "meaning": "the capture was announced on the net for automations to act on",
        "outcomes": ("B",),
        "fields": (("vacuum", "entity_id", None),
                   ("path", "path", None),
                   ("listeners", "int", "count")),
        # `listeners` is the emitter-side half of the silence question, and it costs no
        # coupling: hass.bus.async_listeners() gives a COUNT without naming anyone. Zero
        # means nobody was on the net, so silence is correct and no fault exists — which is
        # the runtime form of the zero-caller class that took a robot-watching session to
        # find in `cancel_active_job`.
        "en": "Announced the capture for {vacuum} at {path} to {listeners} listener(s).",
        "dr": "04 §6a",
    },
}
