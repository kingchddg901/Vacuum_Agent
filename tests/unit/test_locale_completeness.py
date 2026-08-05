"""The BUNDLED card locales must carry every key the English base defines.

WHY THIS EXISTS. `fault.*` — 189 device-error labels plus two fallbacks — shipped
with 0/191 translated in ALL 17 bundled locales, while every other namespace sat
at 100%. A non-English user whose robot threw an error read it in English, on the
one screen where being understood matters most.

Nothing caught it, and the reason is instructive. `scripts/check-i18n.mjs` gates
REACHABILITY: is every key referenced from source? The fault keys are, through a
single `faultLabel` seam (src/state/faults.js) that exists precisely so the gate
sees one template instead of 189 apparently-dead entries. That gate passed and was
right to. Nothing asked the other question — does every locale HAVE the key — so a
namespace added after the last locale sweep landed in the gap between them.

SCOPE: bundled locales only. A user-dropped `<code>.json` in
`config/eufy_vacuum/locales/` is explicitly allowed to be partial (see the folder
README) — untranslated keys fall back to English, which is the point. The files in
this repo are ours, we ship them as complete, and that is the invariant pinned
here.

Coverage targets
----------------
[LOC-1] every bundled locale defines every key in the English base.
[LOC-2] no bundled locale defines a key the English base does not have.
[LOC-3] interpolation placeholders survive translation.
[LOC-4] the en.js parser strips translator notes before reading placeholders.
[LOC-5] no bundled locale contains another language's script (keyboard/paste slips).
"""

from __future__ import annotations

import json
import re
from pathlib import Path

import pytest

_ROOT = Path(__file__).resolve().parents[2]
_EN_JS = _ROOT / "src" / "i18n" / "en.js"
_LOCALES = _ROOT / "custom_components" / "eufy_vacuum" / "frontend" / "locales"

#: CLDR plural categories. A locale stores a pluralised string as an object of
#: these, so the object IS the leaf — flattening into it would report the parent
#: key as missing and every plural key as a false failure.
_PLURAL_KEYS = frozenset({"zero", "one", "two", "few", "many", "other"})

#: Not a translation — a generated copy-from template that is never loaded.
_NOT_A_LOCALE = frozenset({"index", "en.reference"})


def _strip_trailing_comment(value: str) -> str:
    """Drop a trailing `// …` note, respecting quotes and escapes.

    Not optional politeness: nearly every en.js entry carries a translator note,
    and those notes routinely NAME placeholders ("{count}=names.length drives the
    form"). A naive line regex therefore reports `{count}` as expected-and-missing
    in all 17 locales — six such false positives on the first run of this file,
    every one of them the test's fault rather than a translation's.
    """
    out, quote, escaped = [], None, False
    i = 0
    while i < len(value):
        char = value[i]
        if escaped:
            escaped = False
        elif char == "\\":
            escaped = True
        elif quote:
            if char == quote:
                quote = None
        elif char in "\"'":
            quote = char
        elif char == "/" and value[i + 1:i + 2] == "/":
            break
        out.append(char)
        i += 1
    return "".join(out).strip().rstrip(",").strip()


def _english_keys() -> dict[str, str]:
    """Key -> English value with its translator note removed."""
    src = _EN_JS.read_text(encoding="utf-8")
    return {
        key: _strip_trailing_comment(raw)
        for key, raw in re.findall(r'^  "([^"]+)":\s*(.*)$', src, re.MULTILINE)
    }


def _flatten(node, prefix: str = "") -> dict[str, object]:
    out: dict[str, object] = {}
    if isinstance(node, dict) and node and set(node) <= _PLURAL_KEYS:
        out[prefix] = node
    elif isinstance(node, dict):
        for key, value in node.items():
            out.update(_flatten(value, f"{prefix}.{key}" if prefix else key))
    else:
        out[prefix] = node
    return out


def _bundled_locales() -> list[Path]:
    return sorted(
        p for p in _LOCALES.glob("*.json") if p.stem not in _NOT_A_LOCALE
    )


def test_there_are_bundled_locales_to_check():
    """A glob that silently matches nothing would make every test below vacuous."""
    assert len(_bundled_locales()) >= 15


@pytest.mark.parametrize("locale", _bundled_locales(), ids=lambda p: p.stem)
def test_bundled_locale_is_complete(locale: Path):
    """[LOC-1] RELEASE GATE, not a work-blocker — and the failure text says so.

    Adding an English key without its translations fails this immediately, which
    is right at release time and misleading mid-change: ``translate()`` falls back
    to the English base catalog for any missing key, so nothing is broken for a
    user in the meantime. A red bar that reads as "you broke it" when it means
    "do not tag yet" trains people to ignore the bar.
    """
    english = set(_english_keys())
    have = set(_flatten(json.loads(locale.read_text(encoding="utf-8"))))
    missing = sorted(english - have)
    if missing:
        by_ns: dict[str, int] = {}
        for key in missing:
            by_ns[key.split(".")[0]] = by_ns.get(key.split(".")[0], 0) + 1
        summary = ", ".join(f"{ns} ({n})" for ns, n in sorted(by_ns.items()))
        pytest.fail(
            f"RELEASE GATE — {locale.stem}.json is missing {len(missing)} key(s): {summary}"
            f"\n  first few: {missing[:5]}"
            "\n"
            "\n  NOT BROKEN RIGHT NOW: translate() falls back to the English base for"
            "\n  any missing key, so the UI renders English rather than a blank or a"
            "\n  raw key id. Safe to leave red WHILE ITERATING."
            "\n"
            "\n  MUST BE GREEN TO TAG A RELEASE: bundled locales ship complete, and a"
            "\n  stray English string inside a translated pack is a defect the user"
            "\n  sees and cannot fix."
            "\n"
            "\n  To clear: add the keys to the locale files, or — if this namespace is"
            "\n  deliberately English-only — say so here rather than letting it fall"
            "\n  back silently."
        )


@pytest.mark.parametrize("locale", _bundled_locales(), ids=lambda p: p.stem)
def test_bundled_locale_has_no_orphan_keys(locale: Path):
    """[LOC-2] A key the English base dropped is dead weight the loader still
    parses, and usually the sign of a rename applied to en.js alone."""
    english = set(_english_keys())
    have = set(_flatten(json.loads(locale.read_text(encoding="utf-8"))))
    orphans = sorted(have - english)
    assert not orphans, (
        f"{locale.stem}.json defines {len(orphans)} key(s) absent from en.js: "
        f"{orphans[:5]}"
    )


@pytest.mark.parametrize("locale", _bundled_locales(), ids=lambda p: p.stem)
def test_placeholders_survive_translation(locale: Path):
    """[LOC-3] `{code}`, `{count}`, `{error}` are substituted at render time. A
    translation that drops or renames one prints a literal brace at the user, or
    loses the only piece of information the message carried."""
    english = _english_keys()
    flat = _flatten(json.loads(locale.read_text(encoding="utf-8")))
    placeholder = re.compile(r"\{(\w+)\}")

    broken: list[str] = []
    for key, raw_en in english.items():
        want = set(placeholder.findall(raw_en))
        if not want or key not in flat:
            continue
        value = flat[key]
        # A plural leaf carries the placeholder in its forms, not on the object.
        text = " ".join(str(v) for v in value.values()) if isinstance(value, dict) else str(value)
        got = set(placeholder.findall(text))
        if not want <= got:
            broken.append(f"{key}: expected {sorted(want)}, got {sorted(got)}")

    assert not broken, f"{locale.stem}.json placeholder mismatch:\n  " + "\n  ".join(broken[:8])


@pytest.mark.parametrize("raw,expected", [
    # The six shapes that produced false positives on this file's first run.
    ('"This action was refused ({reason})."  // …same convention as {service}).',
     '"This action was refused ({reason})."'),
    ("\"your robot's app\",  // Fragment inserted into 'empty' as {appPhrase}",
     "\"your robot's app\""),
    ('"Water {water} | Recharge {recharge}",  // \'Water\'={ml} used',
     '"Water {water} | Recharge {recharge}"'),
    ('{ one: "{names} was removed", other: "{names} were removed" },  // {count} drives it',
     '{ one: "{names} was removed", other: "{names} were removed" }'),
    # A URL inside the string must NOT be mistaken for a comment.
    ('"See https://example.com/x for help"', '"See https://example.com/x for help"'),
    # No comment at all.
    ('"Plain value"', '"Plain value"'),
])
def test_strip_trailing_comment(raw, expected):
    """[LOC-4] The guard on the guard: if this parser regressed to a naive regex,
    LOC-3 would go quietly green while reading placeholders out of prose."""
    assert _strip_trailing_comment(raw) == expected


# ---------------------------------------------------------------------------
# [LOC-5] no foreign-script contamination in a bundled locale
# ---------------------------------------------------------------------------

#: Scripts a given locale is EXPECTED to contain. A pack may legitimately carry
#: Latin (product names, placeholders, brand words) on top of its own script, so
#: only these four non-Latin scripts are policed — each is unmistakable and each
#: appearing in the wrong pack means a copy/paste or keyboard slip, not a
#: translation choice.
_POLICED_SCRIPTS = ("CYRILLIC", "ARABIC", "HEBREW", "HANGUL")
_EXPECTED_SCRIPT = {"ru": "CYRILLIC", "ar": "ARABIC", "he": "HEBREW", "ko": "HANGUL"}


@pytest.mark.parametrize("locale", _bundled_locales(), ids=lambda p: p.stem)
def test_bundled_locale_has_no_foreign_script(locale):
    """[LOC-5] a pack must not contain a script belonging to another language.

    Added after an Arabic string shipped with two CYRILLIC characters spliced
    into the middle of a word — a keyboard slip that produced a plausible-looking
    string. [LOC-1] passed (the key existed), [LOC-3] passed (placeholders were
    intact), and nothing else looks at the VALUES at all, so it was invisible to
    every existing gate and would have reached Arabic-speaking users as garbage
    inside an otherwise correct sentence.

    Deliberately narrow: only four unmistakable non-Latin scripts are policed,
    and Latin is never flagged, because packs legitimately carry product names,
    brand words and placeholders in Latin.
    """
    import unicodedata

    data = json.loads(locale.read_text(encoding="utf-8"))
    expected = _EXPECTED_SCRIPT.get(locale.stem)

    offenders = []
    for key, value in _flatten(data).items():
        if not isinstance(value, str):
            continue
        present = set()
        for ch in value:
            if not ch.isalpha():
                continue
            try:
                present.add(unicodedata.name(ch).split()[0])
            except ValueError:
                continue
        for script in _POLICED_SCRIPTS:
            if script in present and expected != script:
                offenders.append(f"{key}: unexpected {script}")

    assert not offenders, (
        f"{locale.stem}.json contains characters from another language's script "
        f"(likely a keyboard/paste slip):\n  " + "\n  ".join(sorted(set(offenders))[:10])
    )
