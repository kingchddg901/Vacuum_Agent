"""
Shared string utilities for the rooms subsystem.

Contains pure functions with no HA or brand dependencies that are used
by both the framework room modules and the brand adapters.
"""

import unicodedata


def slugify_room_name(name: str) -> str:
    """Return a stable, URL-safe slug derived from a room name.

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
