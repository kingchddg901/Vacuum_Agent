"""Unit tests for rooms/utils — pure Python, no HA dependency."""

from __future__ import annotations

import unicodedata

from custom_components.eufy_vacuum.rooms.utils import slugify_room_name


def test_slugify_lowercases():
    assert slugify_room_name("Kitchen") == "kitchen"


def test_slugify_spaces_to_underscores():
    assert slugify_room_name("Living Room") == "living_room"


def test_slugify_strips_leading_trailing_whitespace():
    assert slugify_room_name("  bedroom  ") == "bedroom"


def test_slugify_removes_single_quote():
    assert slugify_room_name("master's bedroom") == "masters_bedroom"


def test_slugify_removes_double_quote():
    assert slugify_room_name('"office"') == "office"


def test_slugify_ampersand_to_and():
    assert slugify_room_name("Bath & Shower") == "bath_and_shower"


def test_slugify_already_a_slug():
    assert slugify_room_name("kitchen") == "kitchen"


def test_slugify_empty_string():
    assert slugify_room_name("") == ""


def test_slugify_non_string_coerced():
    assert slugify_room_name(123) == "123"


def test_slugify_multiple_spaces():
    assert slugify_room_name("guest  room") == "guest__room"


def test_slugify_complex_name():
    assert slugify_room_name("Bob's & Alice's Office") == "bobs_and_alices_office"


# --- non-Latin / Unicode identity -------------------------------------------
# Room names are user/cloud-authored and can be any script. The slug is the
# load-bearing reconciliation identity key (rooms/reconciliation.py), so it must
# stay distinct, non-empty, and STABLE across Unicode normalization forms — an
# input axis the original ASCII/English test corpus never exercised.


def test_slugify_preserves_cyrillic_distinct():
    """Cyrillic names keep distinct, non-empty slugs (no ASCII-fold to empty).

    These are the seven rooms from the real Roborock S7 report that surfaced
    this axis. A regex slugifier (``[^a-z0-9]+``) would collapse all seven to
    empty and collide them; the replace-chain preserves them.
    """
    names = [
        "Спальня", "Кабинет", "Зал", "Коридор",
        "Ванная", "Гостевой туалет", "Детская",
    ]
    slugs = [slugify_room_name(n) for n in names]
    assert all(slugs), "a Cyrillic name slugified to empty"
    assert len(set(slugs)) == len(names), "two distinct Cyrillic names collided"
    assert slugify_room_name("Спальня") == "спальня"
    assert slugify_room_name("Гостевой туалет") == "гостевой_туалет"


def test_slugify_preserves_cjk_greek_emoji():
    """General, not Cyrillic-specific: CJK, Greek, and emoji stay distinct."""
    names = ["卧室", "浴室", "Υπνοδωμάτιο", "🛁", "🚽 Guest WC"]
    slugs = [slugify_room_name(n) for n in names]
    assert all(slugs)
    assert len(set(slugs)) == len(names)
    assert slugify_room_name("卧室") == "卧室"
    assert slugify_room_name("🚽 Guest WC") == "🚽_guest_wc"


def test_slugify_mixed_ascii_and_nonlatin_distinct():
    """An ASCII room and a non-Latin room never partial-fold into one key."""
    assert slugify_room_name("Kitchen") != slugify_room_name("卧室")


def test_slugify_nfc_nfd_same_name_same_slug():
    """The SAME name in NFC vs NFD form must derive the SAME slug (stability).

    Precomposed ``Й`` (U+0419) vs ``И`` + combining breve (U+0418 U+0306) are
    visually identical but distinct code points. A brand returning one form on
    first discovery and the other after a re-map must not re-derive a different
    slug and orphan the room's settings. (Red-green of the NFC fix.)
    """
    nfc = unicodedata.normalize("NFC", "Йога")
    nfd = unicodedata.normalize("NFD", "Йога")
    assert nfc != nfd, "inputs must differ at the code-point level"
    assert slugify_room_name(nfc) == slugify_room_name(nfd)
