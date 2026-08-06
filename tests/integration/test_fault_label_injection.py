"""Fault-label INJECTION: drive every declared code through the real seam.

WHY THIS EXISTS. Ivy has 24 clean job records and Alfred 8 with faults, so real
runs exercise 19 of the 238 declared codes and NONE of Roborock's 48. A table that
is never hit is a table nobody notices is broken: a code declared with a key that
has no English string renders a dotted key at the user, and a key missing from one
locale pack renders English inside an otherwise-translated card. Neither shows up
in any other test, because these keys are reached through a TEMPLATE
(``faultLabel`` builds ``fault.${brand}.${slug}``) and so are invisible to
check-i18n's used-key scan.

So we inject instead: every code the adapters declare goes through
``_run_error_rows`` -- the same function the card's history snapshot calls -- and
the resulting key is chased into all 18 shipped languages.

WHAT THIS PROVES: that every declared code resolves, through the real seam, to a
key that has an English string, is translated in all 18 packs, and survives the
card's key splitter.

WHAT IT CANNOT PROVE, stated because a control run showed the obvious reading is
wrong: FLI-1 and FLI-2 compare the seam's answer against the SAME tables the seam
reads, so a table edit moves both sides and they still agree. They are reachability
and normalization gates, not correctness gates -- deleting a code from a source set
does NOT fail them (verified). FLI-2b is the anchor that keeps them meaningful: with
an empty config everything must come back unlabelled and unattributed. Nothing here
validates the taxonomy, or that a device ever emits these codes; those are vendor
and hardware questions. This is a declaration-proving gate
[[feedback_build_for_expansion]].
"""
from __future__ import annotations

import json
import pathlib
import re

import pytest

from custom_components.eufy_vacuum.adapters.registry import (
    clear_registry,
    register_adapter_config,
)
from custom_components.eufy_vacuum.adapters.eufy.vocabulary import (
    EUFY_DOCK_SOURCED_ERROR_CODES,
    EUFY_ERROR_LABEL_KEYS,
    EUFY_ROBOT_SOURCED_ERROR_CODES,
)
from custom_components.eufy_vacuum.adapters.roborock.vocabulary import (
    ROBOROCK_DOCK_SOURCED_ERROR_CODES,
    ROBOROCK_ERROR_LABEL_KEYS,
    ROBOROCK_ROBOT_SOURCED_ERROR_CODES,
)
from custom_components.eufy_vacuum.learning.manager import _run_error_rows

_VAC = "vacuum.injection_rig"
_REPO = pathlib.Path(__file__).resolve().parents[2]
_PACKS = _REPO / "custom_components" / "eufy_vacuum" / "frontend" / "locales"

BRANDS = {
    "eufy": (EUFY_ERROR_LABEL_KEYS, EUFY_DOCK_SOURCED_ERROR_CODES,
             EUFY_ROBOT_SOURCED_ERROR_CODES),
    "roborock": (ROBOROCK_ERROR_LABEL_KEYS, ROBOROCK_DOCK_SOURCED_ERROR_CODES,
                 ROBOROCK_ROBOT_SOURCED_ERROR_CODES),
}


def _english() -> dict[str, str]:
    src = (_REPO / "src" / "i18n" / "en.js").read_text(encoding="utf-8")
    return dict(re.findall(r'"(fault\.[a-z]+\.[a-z0-9_]+)":\s*"([^"]*)"', src))


def _pack(code: str) -> dict:
    return json.loads((_PACKS / f"{code}.json").read_text(encoding="utf-8"))


def _locale_codes() -> list[str]:
    return sorted(
        p.stem for p in _PACKS.glob("*.json")
        if p.stem != "index" and "reference" not in p.stem
    )


def _install(brand: str) -> None:
    """Register the brand's REAL error tables behind a rig entity."""
    labels, dock, robot = BRANDS[brand]
    clear_registry()
    register_adapter_config(_VAC, {
        "adapter_id": f"injection_{brand}",
        "source": "test",
        "error_tracking": {
            "error_label_keys": dict(labels),
            "dock_sourced_error_codes": sorted(dock, key=repr),
            "robot_sourced_error_codes": sorted(robot, key=repr),
        },
    })


def _inject(codes: list) -> list[dict]:
    """Push codes through the exact function the history snapshot uses."""
    outcome = {
        "errors": {
            "error_count": len(codes),
            "errors": [
                {"code": c, "captured_at": "2026-01-01T00:00:00+00:00",
                 "recovered_at": None, "room_id": 1}
                for c in codes
            ],
        }
    }
    # _run_error_rows caps its output; inject in chunks under the cap so every
    # code is actually exercised rather than silently truncated away.
    rows: list[dict] = []
    for i in range(0, len(codes), 10):
        chunk = codes[i:i + 10]
        outcome["errors"]["errors"] = [
            {"code": c, "captured_at": "2026-01-01T00:00:00+00:00",
             "recovered_at": None, "room_id": 1}
            for c in chunk
        ]
        rows.extend(_run_error_rows(_VAC, outcome))
    return rows


@pytest.fixture(autouse=True)
def _clean_registry():
    yield
    clear_registry()


@pytest.mark.parametrize("brand", sorted(BRANDS))
def test_every_declared_code_resolves_through_the_seam(brand):
    """[FLI-1] Inject every code the adapter declares; each comes back NAMED.

    A None here means the card would print the raw vendor code for a fault the
    adapter believes it has a label for.
    """
    labels, _, _ = BRANDS[brand]
    _install(brand)
    codes = list(labels)
    rows = _inject(codes)

    assert len(rows) == len(codes), "the seam dropped injected codes"
    unresolved = [
        (r["code"], r["label_key"]) for r in rows if not r["label_key"]
    ]
    assert not unresolved, f"{brand}: codes declared but unresolved: {unresolved[:8]}"

    for row, code in zip(rows, codes):
        assert row["label_key"] == labels[code], f"{brand} {code}: wrong key"


@pytest.mark.parametrize("brand", sorted(BRANDS))
def test_injected_source_matches_the_declared_sets(brand):
    """[FLI-2] Source attribution is REACHABLE and survives code normalization.

    HONEST SCOPE, because a control run proved the obvious reading false: this
    compares the seam's answer against the same sets the seam reads, so deleting a
    code from a source set changes BOTH sides and the test still passes. It cannot
    detect a wrong taxonomy, and nothing here should be read as validating one --
    that is a hardware/vendor question.

    What it does catch, which is worth having: the seam failing to read the adapter
    config at all, and _code_key normalization breaking so a declared code stops
    matching (the exact failure that made every enum-STRING brand resolve to
    nothing before core carried non-numeric codes). The attribution-count assertion
    below is the part that is not circular -- a broken seam returns all-unknown,
    and that fails here even though the per-code comparison would not.
    """
    labels, dock, robot = BRANDS[brand]
    _install(brand)
    codes = list(labels)
    rows = _inject(codes)

    for row, code in zip(rows, codes):
        expected = "dock" if code in dock else "robot" if code in robot else "unknown"
        assert row["source"] == expected, (
            f"{brand} {code!r}: source {row['source']!r}, tables say {expected!r}"
        )

    # NOT circular: if the seam stopped reading the config, or normalization broke,
    # every code lands on "unknown" and these floors fail.
    attributed = [r for r in rows if r["source"] != "unknown"]
    expected_attributed = sum(1 for c in codes if c in dock or c in robot)
    assert len(attributed) == expected_attributed
    assert expected_attributed > 0, f"{brand}: nothing attributed at all"
    assert any(r["source"] == "robot" for r in rows), f"{brand}: no robot attribution"


@pytest.mark.parametrize("brand", sorted(BRANDS))
def test_attribution_actually_depends_on_the_adapter_config(brand):
    """[FLI-2b] The anchor that makes FLI-1 and FLI-2 mean something.

    Register the rig with an EMPTY error_tracking block and inject the same codes:
    every one must come back unlabelled and unattributed. If this passes while
    FLI-1/FLI-2 also pass, the seam is genuinely reading the adapter's tables
    rather than resolving them some other way -- without it, both of those tests
    could pass against a hardcoded fallback and nobody would know.
    """
    labels, _, _ = BRANDS[brand]
    clear_registry()
    register_adapter_config(_VAC, {
        "adapter_id": f"injection_{brand}_empty",
        "source": "test",
        "error_tracking": {},
    })
    rows = _inject(list(labels)[:10])

    assert rows, "the seam returned nothing at all"
    assert all(r["label_key"] is None for r in rows), (
        "a code resolved to a name with NO table declared -- the label is coming "
        "from somewhere other than the adapter"
    )
    assert all(r["source"] == "unknown" for r in rows), (
        "a code was attributed with NO source sets declared"
    )
    # The raw code still survives, which is what the card falls back to.
    assert all(r["code"] is not None for r in rows)


@pytest.mark.parametrize("brand", sorted(BRANDS))
def test_every_declared_key_has_an_english_string(brand):
    """[FLI-3] A key with no string renders the dotted key at the user.

    This had NO gate for Eufy's 189 keys -- check-i18n cannot see template-built
    keys, and locale completeness compares packs to en.js, never the ADAPTER's
    declarations to en.js.
    """
    labels, _, _ = BRANDS[brand]
    english = _english()
    missing = sorted({k for k in labels.values() if k not in english})
    assert not missing, f"{brand}: declared keys with no English string: {missing}"

    empty = sorted({k for k in labels.values() if not english.get(k, "").strip()})
    assert not empty, f"{brand}: keys whose English string is blank: {empty}"


@pytest.mark.parametrize("brand", sorted(BRANDS))
def test_every_declared_key_is_translated_in_all_18_languages(brand):
    """[FLI-4] A key missing from one pack renders ENGLISH inside a translated
    card. Chase every declared key into all 17 packs (18th is en.js itself)."""
    labels, _, _ = BRANDS[brand]
    wanted = sorted(set(labels.values()))
    gaps: list[str] = []

    for lang in _locale_codes():
        node = _pack(lang).get("fault", {}).get(brand, {})
        for key in wanted:
            slug = key.split(".", 2)[2]
            value = node.get(slug)
            if not isinstance(value, str) or not value.strip():
                gaps.append(f"{lang}:{key}")

    assert not gaps, (
        f"{brand}: {len(gaps)} untranslated declared key(s); first few: {gaps[:8]}"
    )


@pytest.mark.parametrize("brand", sorted(BRANDS))
def test_declared_keys_survive_the_cards_key_splitter(brand):
    """[FLI-5] src/state/faults.js does key.split('.') and REBUILDS the slug with
    parts.slice(2).join('_'). A key with a dot in the slug would silently become a
    different key; fewer than 3 parts is refused outright and renders the raw code.
    """
    labels, _, _ = BRANDS[brand]
    for key in sorted(set(labels.values())):
        parts = key.split(".")
        assert len(parts) >= 3, f"{key}: card refuses a key with <3 parts"
        assert parts[0] == "fault", f"{key}: card only translates fault.* keys"
        assert parts[1] == brand, f"{key}: brand segment must be {brand!r}"
        rebuilt = "_".join(parts[2:])
        assert f"fault.{parts[1]}.{rebuilt}" == key, (
            f"{key}: the card's splitter would rebuild this as "
            f"fault.{parts[1]}.{rebuilt} and look up the wrong string"
        )


def test_an_undeclared_code_is_not_given_a_name():
    """[FLI-6] Control. The injection rig must be capable of returning None, or
    every assertion above passes for the wrong reason."""
    _install("eufy")
    rows = _inject([424242, "not_a_real_enum_state", None])
    assert [r["label_key"] for r in rows] == [None, None, None]
    assert [r["source"] for r in rows] == ["unknown", "unknown", "unknown"]
    # The raw code survives -- it is the card's fallback and must stay greppable.
    assert rows[0]["code"] == 424242
    assert rows[1]["code"] == "not_a_real_enum_state"
