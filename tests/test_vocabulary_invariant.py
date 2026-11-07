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

from custom_components.eufy_vacuum.adapters.brands import BRAND_REGISTRARS
from tests.brand_catalogs import BRAND_BLOCKS, EUFY_BLOCK, ROBOROCK_BLOCK

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
#: add one. EMPTY, and the emptiness is EARNED rather than an artefact -- which it was
#: not until 2026-11-07. The corpus below covered two of three shipped brands, so a
#: leak of a DREAME word could not be reported however plainly core bound it; widening
#: it surfaced one row (learning/manager.py binding clean_intensity to "standard" at
#: two sites), and the same day that row was PAID OFF rather than kept: both sites now
#: default to "" because core has no word for an absent setting, and "standard" was a
#: RETIRED Eufy value being written into the learned room key on every brand. VI-3
#: proves the detector still works in this state and VI-4 holds any future row to
#: describing a LIVE leak, so an empty ledger is evidence here, not absence.
KNOWN_VOCABULARY_LEAKS: dict[str, set[str]] = {}


def _declared_brand_values() -> set[str]:
    """Every string value the shipped adapters declare for a provider-owned field.

    THE CORPUS IS THIS GATE'S ENTIRE SENSITIVITY: a word absent from it cannot be
    reported no matter where core binds it. It used to iterate a hardcoded
    ``(EUFY_BLOCK, ROBOROCK_BLOCK)`` tuple, which was the minimum two brands the
    file's docstring calls for -- and then dreame shipped on 2026-09-13 and the
    tuple did not follow, so for eight weeks this gate was structurally blind to a
    third of the vocabulary it exists to police. The literal read as a deliberate
    floor, which is what made it survive.

    So it is DERIVED from the shipped registry now, not restated. A brand in
    ``BRAND_REGISTRARS`` with no ``BRAND_BLOCKS`` row raises KeyError here, which is
    the loud failure the silent one was hiding behind.
    """
    values: set[str] = set()
    for brand_id in sorted({r.brand_id for r in BRAND_REGISTRARS}):
        block = BRAND_BLOCKS[brand_id]
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


def test_bvl_1_cores_clean_intensity_defaults_all_AGREE():
    """[BVL-1] Every core default for `clean_intensity` is the same, and it is `""`.

    A NEW ID SERIES, deliberately. This file's VI-1..VI-4 collide with
    `tests/unit/test_vacuum_identity.py`, which owns VI-1..VI-8 for an unrelated
    subject; VI-5 is already taken there. Renumbering that file's ids is a
    separate decision, so this starts BVL (brand-vocabulary-leak) rather than
    making the clash three-way.

    VI-1 catches a BRAND WORD coming back. It cannot catch the other failure this
    field has, which is the sites DISAGREEING with each other.

    `clean_intensity` is part of the learned-room MATCH KEY. `learning/manager.py`
    builds that key in three places -- the accuracy projection, the estimate
    projection, and the lookup that reads learned stats -- and a key is only a key if
    every site spells the absent case identically. Until 2026-11-07 the lookup
    defaulted to `""` while the two projections defaulted to `"standard"`, which was
    both a retired Eufy word (VI-1's concern) and a WRITER/READER DISAGREEMENT: a room
    that never had an intensity was recorded under one bucket and looked up in another.

    The tempting repair is the one this test exists to stop. "Read the default from the
    adapter's declaration" is the right instinct for a brand word in core, and
    `profiles/room_profiles.py::default_setting_values` would supply it -- eufy
    declares `Quick`. Applied to these sites it would re-open the disagreement from the
    other side, because the lookup has no room data to derive from and correctly
    answers `""`: a room with no intensity set is a DIFFERENT bucket from one
    explicitly set to the brand's default, and conflating them manufactures a
    permanent mismatch penalty out of a fix.

    So the rule is agreement, and the agreed value is the one that holds no brand's
    word at all (IN40W49E -- undeclared resolves EMPTY).

    AST-based because this IS a source-consistency property: there is no single runtime
    call that observes all three sites. Same instrument as `vocabulary_bindings` above.
    The count is asserted first, so a refactor that moves these sites fails loudly here
    instead of turning the comparison into a pass over nothing.
    """
    path = os.path.join(CORE, "learning", "manager.py")
    tree = ast.parse(open(path, encoding="utf-8").read())

    defaults: list[tuple[int, object]] = []
    for node in ast.walk(tree):
        # `room.get("clean_intensity", <default>)` / `protected.get(...)` -- the
        # two-argument .get is how every one of these sites spells the default.
        if not isinstance(node, ast.Call):
            continue
        fn = node.func
        if not (isinstance(fn, ast.Attribute) and fn.attr == "get"):
            continue
        if len(node.args) != 2:
            continue
        key = node.args[0]
        if not (isinstance(key, ast.Constant) and key.value == "clean_intensity"):
            continue
        d = node.args[1]
        defaults.append((node.lineno, d.value if isinstance(d, ast.Constant) else ast.dump(d)))

    # PINNED AT THE MEASURED COUNT, not a loose floor. The first draft said `>= 3`
    # and did NOT bite when a site was reshaped out of the extraction's reach: there
    # are FIVE, so four still cleared three. A floor that cannot notice a site
    # leaving is the same vacuity it was written to prevent. Measured 2026-11-07:
    # lines 1406, 2018, 2019, 2830, 2943 -- two of which (1406, 2830) are the sites
    # this change corrected; the other three were already "".
    assert len(defaults) == 5, (
        f"expected exactly 5 clean_intensity defaults in learning/manager.py, found "
        f"{len(defaults)}: {defaults}. If a site was legitimately added or removed, "
        f"update this count DELIBERATELY -- it is here so that a site slipping out "
        f"of the extraction's reach cannot make the agreement check pass over a subset."
    )

    disagreeing = {v for _ln, v in defaults}
    assert disagreeing == {""}, (
        "core's clean_intensity defaults must all be the empty string, and they must "
        "AGREE -- this field is part of the learned-room match key.\n"
        + "\n".join(f"  learning/manager.py:{ln} -> {v!r}" for ln, v in sorted(defaults))
        + "\n\nA writer and a reader that disagree on the absent case put a room into "
          "one bucket and look it up in another. Reading the brand's DECLARED default "
          "here does not fix that, it re-opens it from the other side: see this test's "
          "docstring."
    )
