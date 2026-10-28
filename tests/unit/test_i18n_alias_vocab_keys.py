"""Every display spelling an adapter accepts must have a card vocabulary key.

A room's STORED setting is an un-normalized display string, not a canonical code. The
learning normalizer canonicalizes what it emits, but the surfaces that render a room's
stored value untouched — the rooms-view chips, the standalone room card, the map
selection bar's per-room summary, the external-run summary — slug THAT string. So
``vocab.clean_mode.vacuum_mop`` does not cover a room whose stored value is
``"Vacuum and mop"``; that needs its own ``vocab.clean_mode.vacuum_and_mop``.

``docs/dev/frontend/i18n-system.md`` states the contract — *"Add a display spelling to an
adapter's alias map and you must add the matching alias key, or that surface silently
reverts to English for every language"* — and nothing enforced it. Nine spellings had no
key when this was written, which is why the sinks that DO call ``tVocab`` still rendered
English for them: a correct call against a missing key falls back, silently, to the
backend's word. That is what makes this a gate and not a style note.

An alias carries its CANONICAL rung's word, never a translation of its own spelling
([AVK-3]). Two rooms set to the same water level must not read as two different settings
because one of them was saved under an older spelling.

THE FLOOR THIS DOES NOT COVER, stated rather than implied: Roborock builds
``water_level``/``path_type`` aliases at runtime from the device's own option list
(``build_positional_aliases``), so those display words are not knowable here and cannot
be pre-keyed. They are carried by ``tVocab``'s documented fallback — the adapter's
declared label — and localizing them is part of the per-install vocabulary question in
``SCOPE-71``, not of this contract. [AVK-4] pins that the dynamic builder is what makes
them exempt, so the exemption dies with the code rather than outliving it.

Coverage targets
----------------
[AVK-1] every statically declared alias spelling has a ``vocab.<field>.<slug>`` key.
[AVK-2] the mutation control: an invented spelling with no key is detected.
[AVK-3] an alias key's English equals its canonical target's English.
[AVK-4] the runtime-built Roborock aliases are exempt because they are runtime-built.
"""

from __future__ import annotations

import pathlib
import re

import pytest

from custom_components.eufy_vacuum.adapters.eufy import vocabulary as eufy_vocab
from custom_components.eufy_vacuum.adapters.roborock import vocabulary as rr_vocab

REPO = pathlib.Path(__file__).resolve().parents[2]
EN_JS = REPO / "src" / "i18n" / "en.js"

#: field -> {display spelling: canonical value}. Only STATICALLY declared maps: these are
#: the spellings that exist in the source and can therefore be keyed ahead of time.
STATIC_ALIAS_MAPS: dict[str, dict[str, str]] = {
    "clean_mode": dict(eufy_vocab.CLEAN_MODE_ALIASES),
    "clean_intensity": dict(eufy_vocab.CLEAN_INTENSITY_ALIASES),
    "fan_speed": dict(eufy_vocab.FAN_SPEED_ALIASES),
    "water_level": dict(eufy_vocab.WATER_LEVEL_ALIASES),
}


def card_slug(value: str) -> str:
    """The card's slug rule, from src/cards/_shared.js::vocab and renderers/shared.js.

    Mirrored rather than imported because the owner is JavaScript. The two must agree:
    a divergence here aims this gate at keys the card never looks up.
    """
    return re.sub(r"[^a-z0-9]+", "_", str(value).lower()).strip("_")


def en_keys() -> dict[str, str]:
    """Every flat `"key": "value"` pair in en.js, read as text.

    en.js is a JS module, so it cannot be imported here; but its keys are flat quoted
    strings, which makes an exact scan possible without parsing JavaScript.
    """
    out: dict[str, str] = {}
    for line in EN_JS.read_text(encoding="utf-8").splitlines():
        match = re.match(r'\s*"([a-z0-9_.]+)"\s*:\s*"((?:[^"\\]|\\.)*)"\s*,', line)
        if match:
            out[match.group(1)] = match.group(2)
    return out


def unkeyed_spellings(alias_maps: dict[str, dict[str, str]], keys: dict[str, str]) -> list[str]:
    """The alias spellings in `alias_maps` with no `vocab.<field>.<slug>` key in `keys`."""
    missing: list[str] = []
    for field, aliases in alias_maps.items():
        for spelling in aliases:
            key = f"vocab.{field}.{card_slug(spelling)}"
            if key not in keys:
                missing.append(f"{key}  (stored spelling {spelling!r})")
    return sorted(missing)


def test_avk_1_every_declared_alias_spelling_has_a_vocab_key() -> None:
    """[AVK-1]"""
    keys = en_keys()
    assert len(keys) > 2000, f"en.js scan found only {len(keys)} keys — the scanner is broken"

    missing = unkeyed_spellings(STATIC_ALIAS_MAPS, keys)
    assert not missing, (
        "an adapter accepts these display spellings but the card has no key for them, so "
        "every surface that renders a room's stored value reverts to English:\n  "
        + "\n  ".join(missing)
    )


def test_avk_2_an_unkeyed_spelling_is_detected() -> None:
    """[AVK-2] the mutation control — [AVK-1] passing must mean something.

    Runs the SAME function over an alias map with one spelling nobody has keyed. A gate
    that cannot name the input that makes it red is a preference.
    """
    keys = en_keys()
    injected = {f: dict(m) for f, m in STATIC_ALIAS_MAPS.items()}
    injected["clean_mode"]["Vacuum, mop and polish"] = "vacuum_mop"

    missing = unkeyed_spellings(injected, keys)
    assert missing == ["vocab.clean_mode.vacuum_mop_and_polish  "
                       "(stored spelling 'Vacuum, mop and polish')"], missing
    # And the real table is still clean, so the injection is what produced that one hit.
    assert not unkeyed_spellings(STATIC_ALIAS_MAPS, keys)


def test_avk_3_clean_mode_aliases_all_read_as_the_one_phrase() -> None:
    """[AVK-3] — scoped to clean_mode, and the scope is the finding.

    A first draft of this asserted it for EVERY axis and went red on the tree, correctly:
    ``clean_intensity.standard`` reads "Standard" while its canonical target ``narrow``
    reads "Narrow", annotated in en.js as the Eufy app term. That is deliberate. An alias
    spelling on the suction / water / path axes IS the brand's own app word, and replacing
    it with core's internal key word would put "Narrow" in front of an owner whose app says
    "Standard" — the inversion ``f/eufy_is_not_the_default`` is about, pointed the other way.

    clean_mode is the exception because every brand names that axis with the same phrase
    (Eufy, Roborock and Dreame all ship "Vacuum and mop" or a spelling of it), so its
    aliases are loose spellings of ONE word rather than three competing app terms — and two
    rooms in the same mode reading as two different modes is then a real defect.
    """
    keys = en_keys()
    canonical_word = keys["vocab.clean_mode.vacuum_mop"]
    wrong = {
        f"vocab.clean_mode.{card_slug(spelling)}": keys[f"vocab.clean_mode.{card_slug(spelling)}"]
        for spelling in STATIC_ALIAS_MAPS["clean_mode"]
        if f"vocab.clean_mode.{card_slug(spelling)}" in keys
        and keys[f"vocab.clean_mode.{card_slug(spelling)}"] != canonical_word
    }
    assert not wrong, (
        f"every clean_mode spelling must read as {canonical_word!r}; these do not: {wrong}"
    )
    # Not vacuous: there is more than one spelling, and they are not all the canonical key.
    assert len(STATIC_ALIAS_MAPS["clean_mode"]) >= 3


def test_avk_4_roborock_aliases_are_runtime_built_and_therefore_exempt() -> None:
    """[AVK-4] anchor the exemption to the code that causes it."""
    assert hasattr(rr_vocab, "build_positional_aliases"), (
        "the Roborock exemption in this module's docstring rests on these aliases being "
        "DERIVED from the device's live option list. If that builder is gone, the aliases "
        "are static now and belong in STATIC_ALIAS_MAPS above."
    )
    # Identical ladders retire nothing, so the map is empty and there is nothing to key.
    assert rr_vocab.build_positional_aliases(["off", "low"], ["off", "low"]) == {}
    # A moved ladder produces DEVICE words as targets — unknowable at test time, which is
    # exactly why they cannot be pre-keyed.
    moved = rr_vocab.build_positional_aliases(
        ["off", "low", "medium", "high"], ["off", "mild", "standard", "intense"]
    )
    assert moved, "a moved ladder must produce aliases, or this exemption describes nothing"
    assert set(moved.values()) - {"off", "low", "medium", "high"}, (
        "the alias TARGETS must be the device's own words, not canonical ones"
    )


@pytest.mark.parametrize("field", sorted(STATIC_ALIAS_MAPS))
def test_alias_maps_are_non_empty(field: str) -> None:
    """A gate over an empty table passes and proves nothing (an EMPTY DICT passes everything)."""
    assert STATIC_ALIAS_MAPS[field], (
        f"{field} declares no aliases — if that is now true, remove it from "
        "STATIC_ALIAS_MAPS rather than leaving a vacuous row behind"
    )
