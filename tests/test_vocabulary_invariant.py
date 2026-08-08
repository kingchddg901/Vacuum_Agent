"""INVARIANT: core owns the KEY space. It does not own any brand's WORDS.

Eufy arrived first, so its vocabulary was written as the framework's. Every instance of
that was invisible from inside — the code reads as principled, an Eufy-only suite passes,
and the damage appears only on another brand, where the inherited word is absent from
that device's declared options and is dropped before it reaches the wire. Nothing logs.

The rule this gate enforces is narrower and more useful than "no Eufy words in core":

  **Core may own internal canonical vocabulary. Core may not assume that a PROVIDER's
  vocabulary equals that canonical vocabulary.**

So it takes TWO signals together, and a hit needs both:

  1. **Syntactic** — the literal is bound to a provider-owned field (assigned to it,
     used as its default, compared against it, passed as it).
  2. **Lexical** — the literal is a value some adapter actually DECLARES, and is not in
     the explicitly core-owned set below.

Either signal alone is useless. Lexical alone reports every ``max``, ``off`` and ``low``
in four thousand tests and a hundred modules — `wash_frequency_bounds["max"]` is a
structural key, `confidence == "low"` is a confidence level, `state == "off"` is an HA
entity state, and a gate that screams at those is one everybody learns to ignore.
Syntactic alone cannot tell a canonical key from a brand's word.

CORE_OWNED is the load-bearing declaration here. It is the written statement of what
belongs to the framework, and every entry needs a reason a reviewer would accept.
Growing it to silence a finding is how this gate dies.

**Case-sensitive, deliberately — do not "fix" this.** Folding case would catch a couple
more strings and destroy the gate's main purpose: Eufy's ``"Off"`` and the canonical
``"off"`` would become the same token, so ``"Off"`` would be swallowed by CORE_OWNED and
the five real leaks this found in ``apply_capability_gate`` and ``_protected_room_config``
would be invisible. ``"Off"`` vs ``"off"`` IS the bug — a Roborock device rejects the
first and accepts the second.

The consequence is a known and accepted blind spot: values a brand has RETIRED are not
declared anywhere, so this cannot see them. That is the store migration's job
(``rooms/vocabulary_migration.py``), which reaches them without a retired-value map by
resetting anything absent from the brand's declared options.
"""

from __future__ import annotations

import ast
import os

import pytest

from tests.brand_catalogs import EUFY_BLOCK, ROBOROCK_BLOCK

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
CORE = os.path.join(REPO, "custom_components", "eufy_vacuum")

#: Fields whose VALUES are a provider's vocabulary. ``clean_mode`` and ``path_type`` are
#: deliberately absent: their values (vacuum/mop/vacuum_mop, wide/narrow) are framework
#: canonicals that every brand maps ONTO, so a literal there is core using its own word.
PROVIDER_FIELDS = frozenset({"fan_speed", "water_level", "clean_intensity"})

#: What the framework legitimately owns. Each entry is a claim, not a suppression:
CORE_OWNED = frozenset({
    # The canonical water estimator key space (planning/run_plan.py). Core keys its rate
    # table on these and brands map into them via declared water_level_aliases; proven
    # independently of both brands by tests/unit/test_water_vocabulary_boundary.py.
    "off", "low", "medium", "high",
    # Canonical clean_mode / path_type values, listed because a brand may declare them
    # as its own too (Roborock's path_type IS wide/narrow).
    "vacuum", "mop", "vacuum_mop", "wide", "narrow",
    # "nobody said" — the value core writes when nothing is declared.
    "",
})

#: Shrink-only ratchet. A row is a leak that EXISTS and is tolerated, never a licence to
#: add one. Empty as of 2026-08-07; VI-3 proves the detector still works in that state,
#: so an empty ledger is evidence rather than absence.
KNOWN_VOCABULARY_LEAKS: dict[str, set[str]] = {}


def _declared_brand_values() -> set[str]:
    """Every string value the shipped adapters declare for a provider-owned field."""
    values: set[str] = set()
    for block in (EUFY_BLOCK, ROBOROCK_BLOCK):
        for profile in block["builtins"].values():
            values |= {
                str(v) for k, v in profile.items()
                if k in PROVIDER_FIELDS and isinstance(v, str)
            }
        template = block.get("custom_template") or {}
        values |= {
            str(v) for k, v in template.items()
            if k in PROVIDER_FIELDS and isinstance(v, str)
        }
        for key in ("floor_type_water_defaults", "floor_type_fan_defaults"):
            values |= {str(v) for v in (block.get(key) or {}).values()}
    return values - CORE_OWNED


def _is_str(node: ast.AST) -> bool:
    return isinstance(node, ast.Constant) and isinstance(node.value, str)


def _target_field(node: ast.AST) -> str | None:
    """The provider field this assignment target names, if any."""
    if isinstance(node, ast.Name) and node.id in PROVIDER_FIELDS:
        return node.id
    if isinstance(node, ast.Subscript) and _is_str(node.slice):
        if node.slice.value in PROVIDER_FIELDS:
            return node.slice.value
    if isinstance(node, ast.Attribute) and node.attr in PROVIDER_FIELDS:
        return node.attr
    return None


def vocabulary_bindings(tree: ast.AST):
    """Yield (lineno, field, literal) for every string bound to a provider field.

    Deliberately covers the four shapes the real leaks took, which is not an arbitrary
    list — each is a site where one of them actually lived:
      dict entry        {"fan_speed": "Max"}          apply_run_profile
      assignment        water_level = "Off"           apply_capability_gate ×3
      subscript assign  protected["water_level"]="Off"  _protected_room_config ×2
      .get() default    .get("fan_speed", "Max")      normalize_room_profile
    Plus keyword args and comparisons, which are the same binding in other clothes.
    """
    for node in ast.walk(tree):
        if isinstance(node, ast.Dict):
            for key, value in zip(node.keys, node.values):
                if key is not None and _is_str(key) and _is_str(value):
                    if key.value in PROVIDER_FIELDS:
                        yield value.lineno, key.value, value.value

        elif isinstance(node, ast.Assign) and _is_str(node.value):
            for target in node.targets:
                field = _target_field(target)
                if field:
                    yield node.value.lineno, field, node.value.value

        elif isinstance(node, ast.Call):
            func = node.func
            if (isinstance(func, ast.Attribute) and func.attr == "get"
                    and len(node.args) == 2
                    and _is_str(node.args[0]) and _is_str(node.args[1])
                    and node.args[0].value in PROVIDER_FIELDS):
                yield node.args[1].lineno, node.args[0].value, node.args[1].value
            for kw in node.keywords:
                if kw.arg in PROVIDER_FIELDS and _is_str(kw.value):
                    yield kw.value.lineno, kw.arg, kw.value.value

        elif isinstance(node, ast.Compare):
            field = _target_field(node.left)
            if field:
                for comparator in node.comparators:
                    if _is_str(comparator):
                        yield comparator.lineno, field, comparator.value


def _core_files() -> list[tuple[str, str]]:
    """(relpath, abspath) for every core .py — adapters/ excluded, that is their job."""
    out: list[tuple[str, str]] = []
    for root, dirs, files in os.walk(CORE):
        dirs[:] = [d for d in dirs if d not in ("__pycache__", "adapters")]
        for name in sorted(files):
            if name.endswith(".py"):
                path = os.path.join(root, name)
                rel = os.path.relpath(path, CORE).replace("\\", "/")
                out.append((rel, path))
    return out


def _leaks() -> list[str]:
    brand_values = _declared_brand_values()
    found: list[str] = []
    for rel, path in _core_files():
        allowed = KNOWN_VOCABULARY_LEAKS.get(rel, set())
        try:
            tree = ast.parse(open(path, encoding="utf-8").read())
        except SyntaxError:  # pragma: no cover - a broken file fails elsewhere, loudly
            continue
        for lineno, field, literal in vocabulary_bindings(tree):
            if literal in brand_values and literal not in allowed:
                found.append(f"{rel}:{lineno} {field}={literal!r}")
    return sorted(found)


def test_vi_1_core_binds_no_brand_word_to_a_provider_field():
    """[VI-1] The invariant itself.

    Every entry below is core deciding what a device should do using a word only one
    brand speaks. On any other brand the value is absent from the declared options,
    dispatch drops it, and the setting silently does nothing.
    """
    leaks = _leaks()
    assert not leaks, (
        "Core binds a brand's vocabulary to a provider-owned field:\n  "
        + "\n  ".join(leaks)
        + "\n\nRead the value from the adapter's DECLARATION instead — "
          "`no_water_value(catalog)`, the catalog's `default_profile`, or the brand's "
          "`custom_template`. Do not relocate the literal, and do not add it to "
          "CORE_OWNED unless it is genuinely a framework canonical that every brand "
          "maps onto: that list is the written statement of what core owns, and "
          "growing it to silence a finding is how this gate stops working."
    )


def test_vi_2_the_premise_holds_the_brands_actually_differ():
    """[VI-2] VI-1 is vacuous if every brand spells everything the same way."""
    values = _declared_brand_values()
    assert values, (
        "No brand-declared vocabulary left to scan for. Either the adapters stopped "
        "declaring their own words, or CORE_OWNED has grown to swallow all of them — "
        "and VI-1 is now green because it is checking nothing."
    )
    eufy = {
        str(v) for p in EUFY_BLOCK["builtins"].values()
        for k, v in p.items() if k in PROVIDER_FIELDS and isinstance(v, str)
    } - CORE_OWNED
    roborock = {
        str(v) for p in ROBOROCK_BLOCK["builtins"].values()
        for k, v in p.items() if k in PROVIDER_FIELDS and isinstance(v, str)
    } - CORE_OWNED
    assert eufy and roborock and eufy != roborock, (
        f"The two brands must declare DIFFERENT words for VI-1 to mean anything. "
        f"eufy={sorted(eufy)} roborock={sorted(roborock)}"
    )


@pytest.mark.parametrize("source,expected", [
    ('water_level = "Max"', True),                      # bare assignment
    ('room["fan_speed"] = "Max"', True),                # subscript assignment
    ('x = {"clean_intensity": "Quick"}', True),         # dict entry
    ('v = s.get("fan_speed", "Max")', True),            # .get default
    ('f(fan_speed="Max")', True),                       # keyword argument
    ('if room["water_level"] == "Off": pass', True),    # comparison
    ('bounds = {"max": 3}', False),                     # a structural KEY named max
    ('if confidence == "low": pass', False),            # unrelated field, canonical word
    ('water_level = "off"', False),                     # core-owned canonical
    ('label = "Max"', False),                           # not bound to a provider field
    ('fan_speed = declared["fan_speed"]', False),       # read from a declaration
])
def test_vi_3_the_detector_detects(source, expected):
    """[VI-3] The instrument, exercised — positive AND negative.

    A gate only ever seen passing has not been tested, and this one will spend its whole
    life green if it works. The negative rows matter more than the positive ones: they
    are the false-positive classes that made a naive lexical scan unusable, and the
    reason `bounds["max"]` and `confidence == "low"` do not appear in VI-1's output.
    """
    brand_values = {"Max", "Off", "Quick", "Standard", "balanced", "turbo"}
    hits = [
        lit for _, _, lit in vocabulary_bindings(ast.parse(source))
        if lit in brand_values
    ]
    assert bool(hits) is expected, f"{source!r} -> {hits}"


def test_vi_4_the_ledger_is_empty_and_that_is_a_claim():
    """[VI-4] Hygiene: a paid-off entry must leave, or the ledger rots into noise.

    Same discipline as ISO-2 and mock_allowlist.json — shrink-only, and an entry that no
    longer describes a real leak is removed rather than left as decoration.
    """
    brand_values = _declared_brand_values()
    stale = []
    for rel, words in KNOWN_VOCABULARY_LEAKS.items():
        path = os.path.join(CORE, rel)
        if not os.path.exists(path):
            stale.append(f"{rel} (file is gone)")
            continue
        tree = ast.parse(open(path, encoding="utf-8").read())
        live = {lit for _, _, lit in vocabulary_bindings(tree) if lit in brand_values}
        for word in sorted(words - live):
            stale.append(f"{rel}: {word!r} is no longer bound anywhere in that file")
    assert not stale, (
        "Ledger entries that no longer describe a real leak:\n  " + "\n  ".join(stale)
        + "\n\nDelete them. The debt is paid and the ledger should not outlive it."
    )
