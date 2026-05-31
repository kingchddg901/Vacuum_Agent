"""Unit tests for rooms/utils — pure Python, no HA dependency."""

from __future__ import annotations

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
