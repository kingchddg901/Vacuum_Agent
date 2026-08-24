"""
Shared string utilities for the rooms subsystem.

Contains pure functions with no HA or brand dependencies that are used
by both the framework room modules and the brand adapters.
"""

import unicodedata


def slugify_room_name(name: str) -> str:
    """Return a stable slug derived from a room name. NOT URL-safe.

    ⚠ was: "a stable, URL-safe slug" — false, and contradicted three lines later by
    this same docstring (RM24). Percent-encode before putting a slug in a URL. The
    transform lower-cases, strips outer whitespace, deletes the ASCII ``'`` and
    ``"``, maps ``&`` to ``and``, maps the ASCII SPACE to ``_``, and NFC-normalizes
    — and does nothing else. So a slug can still carry: any non-ASCII codepoint
    (deliberately — see below), typographic quotes (U+2018/U+2019/U+201C/U+201D are
    NOT the two that get deleted), tabs and other whitespace that is not U+0020, and
    reserved URL characters such as ``/``, ``?``, ``#`` and ``%``. STABLE is the
    property that is true and the property callers actually need.

    The slug is the room's *load-bearing identity key*: reconciliation
    (``rooms/reconciliation.py``) and the learning baselines key durable data on
    it across a re-segment, so two invariants matter — distinct names must yield
    distinct slugs, and the SAME name must yield the SAME slug every time it is
    rediscovered.

    The transform is intentionally script-agnostic: it lower-cases and
    substitutes a few separators but never strips non-ASCII, so Cyrillic / Greek
    / CJK / emoji room names keep distinct, non-empty slugs. (An ASCII-folding
    slugifier would collapse an all-non-Latin name to empty and collide every
    such room into a single identity — the exact data-loss case reconciliation
    exists to prevent.)

    Names are canonicalized to Unicode NFC so a name arriving in a different
    normalization form across re-maps — e.g. precomposed ``Й`` (U+0419) vs
    ``И`` + combining breve (U+0418 U+0306): visually identical, different code
    points — still derives the same slug. Without it, a brand returning NFD on
    one firmware and NFC on another would re-derive a different slug for the same
    room and orphan its settings on the next re-segment. NFC is a no-op for
    ASCII, so existing ASCII slugs are unchanged.
    """
    return unicodedata.normalize(
        "NFC",
        str(name)
        .strip()
        .lower()
        .replace("'", "")
        .replace('"', "")
        .replace("&", "and")
        .replace(" ", "_"),
    )
