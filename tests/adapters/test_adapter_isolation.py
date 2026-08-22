"""An adapter is not an adapter if it gets to cheat.

A brand package translates VA's meaning into one provider's vocabulary. It is an
EDGE, and it is meant to be substitutable: Eufy falls out, Roborock takes its
place, nothing above changes. That property is only real if the adapter cannot
reach inward — the moment a brand package imports core semantics, "adapter"
becomes a filing convention rather than an architecture.

`test_adapter_contract.py` already asserts what a brand must DECLARE. Nothing
asserted what a brand may TOUCH, so this file does.

WHY FOUR CHECKS AND NOT ONE. Measuring this on 2026-08-07 produced two wrong
answers from instruments that were each individually reasonable:

  * a ``^from``-anchored grep reported the Roborock adapter as reaching nothing.
    It reaches ``core.capabilities`` through a DEFERRED import inside a function —
    deferred precisely to dodge an import cycle, which is to say the dependency is
    real and the narrow instrument was hiding it. Hence: AST, every node, every
    file, not just module level.
  * an import graph cannot see a RUNTIME reach at all. An adapter handed ``hass``
    or a manager can touch anything without importing it, so import-only proof of
    isolation is not proof.

Checks 3 and 4 are currently clean and are expected to stay that way. They are
here because their absence is the interesting result, and a check only added
after the first violation would have nothing to say about how long it had been
true.

[ISO-1] no brand package imports outside the declared SDK
[ISO-2] the known-leak allowlist is SHRINK-ONLY
[ISO-3] no dynamic import escapes the static check
[ISO-4] no runtime reach into a passed-in object's privates
[ISO-5] the detector detects — the instrument is exercised against a real leak
"""

from __future__ import annotations

import ast
import textwrap
import os

ADAPTERS = os.path.join(
    os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))),
    "custom_components",
    "eufy_vacuum",
    "adapters",
)

# The adapter-facing SDK: things a brand package is ENTITLED to use. Both entries
# were adjudicated from measurement, not assumed.
#
#   core.capabilities        — BOTH shipped brands call detect_capabilities(). A
#                              facility every adapter needs is API that happens to
#                              live in core/, not a private internal being reached
#                              around.
#   mapping.segment_primitives — brand-neutral geometry: rdp, polygon_area,
#                              mask_to_polygon, mask_iou, compactness. No Eufy
#                              semantics anywhere in it. Any brand that ships a map
#                              IMAGE needs it; Roborock supplies segments directly
#                              and imports none of it. That every current CV brand
#                              happens to be Eufy is a fact about today's brand
#                              list, not about the primitive.
ALLOWED_SDK = (
    "core.capabilities",
    "mapping.segment_primitives",
)

# SHRINK-ONLY, same discipline as tests/mock_allowlist.json. An entry here is a
# known architectural debt with a named owner, not a permission.
#
#   profiles.room_profiles — the last IMPORT leak (verified 2026-08-07 across all
#   four checks below). The framework's in-code profile catalog IS Eufy's: Eufy was
#   the first brand, so the catalog was written as "the" catalog and the adapter
#   imports it to declare itself. Roborock already demonstrates the fix — it
#   declares its vocabulary in adapters/roborock/vocabulary.py and imports nothing
#   from profiles/.
#
#   SCHEDULED: folded into the finding batch of the adapter-boundary sweep
#   (.claude/notes/synthesis/DESIGN-semantic-taint-sweep.md), not fixed
#   standalone — Chris, 2026-08-07. Two reasons, and the second is the real one:
#     * removing it is a STORED-DATA change, not a refactor. Those values are
#       written onto existing rooms and the card compares option values strictly,
#       so one differing character silently changes what a saved room means.
#     * it is the SEED of a class, not an isolated defect. This same catalog is
#       also the known BEHAVIORAL fossil (a brand omitting its own block inherits
#       Eufy's fan speeds — the Roborock no-suction incident in dev doc 21 §7).
#       The sweep is expected to surface siblings; fixing them as one
#       canonicalization change, one docs absorption and one stored-data
#       migration is safer than three separate touches on room vocabulary.
#
#   So this entry is expected to persist until that batch lands. It is scheduled
#   debt with a named owner, which is exactly what an allowlist entry is for.
#: Ratchet: shrink-only. An entry here is a leak that EXISTS and is being tolerated
#: until it is cut, never a licence to add one. Empty since 2026-08-07, when
#: ``eufy/adapter.py``'s import of ``profiles.room_profiles`` was cut — Eufy's
#: vocabulary now lives in ``adapters/eufy/room_profiles.py`` and core holds none.
#: Adding a row needs a reason a reviewer would accept; ISO-5 proves the detector
#: still works with this dict empty, so an empty ledger is evidence, not absence.
KNOWN_LEAKS: dict[str, set[str]] = {}

#: Reaching into ANOTHER HA integration's ``hass.data`` is the adapter's whole job
#: (robovac_mqtt for Eufy, roborock for Roborock). Only VA's OWN domain is fenced —
#: a brand file reading ``hass.data[DOMAIN]`` is reading core's runtime state.
#:
#: Consumed by ISO-6. Until 2026-08-21 NOTHING consumed it: it was declared, its rule
#: lived in the comment above, and no test could make that rule fail — a PREFERENCE
#: wearing a claim's clothes (ledger C45c). It is now the fence's vocabulary.
OWN_DOMAIN_KEYS = ("DOMAIN", "eufy_vacuum")


def _brand_files() -> list[tuple[str, str]]:
    """(relpath, abspath) for every .py under adapters/, excluding caches."""
    out: list[tuple[str, str]] = []
    for root, dirs, files in os.walk(ADAPTERS):
        dirs[:] = [d for d in dirs if d != "__pycache__"]
        for fname in sorted(files):
            if not fname.endswith(".py"):
                continue
            path = os.path.join(root, fname)
            rel = os.path.relpath(path, ADAPTERS).replace("\\", "/")
            out.append((rel, path))
    return out


def _escaping_imports(path: str) -> list[tuple[int, str]]:
    """Modules imported from OUTSIDE the adapters package.

    Catches both `from ...pkg.mod import x` (level >= 3 leaves adapters/brand/)
    and an absolute `import custom_components.eufy_vacuum.pkg`. Walks every node,
    so a deferred import inside a function body is caught exactly like a
    module-level one — the distinction that made a grep lie about Roborock.
    """
    tree = ast.parse(open(path, encoding="utf-8").read())
    found: list[tuple[int, str]] = []
    for node in ast.walk(tree):
        if isinstance(node, ast.ImportFrom):
            if node.level and node.level >= 3 and node.module:
                found.append((node.lineno, node.module))
        elif isinstance(node, ast.Import):
            for alias in node.names:
                if "eufy_vacuum" in alias.name:
                    found.append((node.lineno, alias.name.split("eufy_vacuum.")[-1]))
    return found


def test_iso_1_no_brand_package_imports_outside_the_declared_sdk():
    """[ISO-1] A brand package reaches only the SDK, or a ledgered known leak."""
    offenders: list[str] = []
    for rel, path in _brand_files():
        # registry.py and brands.py are the adapter TIER, not a brand package.
        # Their reaches are registry LOOKUPS (known_dispatch_templates,
        # get_segmenter_engine, get_room_attribution_engine, KNOWN_CAPABILITY_HINTS)
        # — resolving a brand's declared engine name to an implementation is the
        # validation seam doing its job, not a brand cheating.
        if "/" not in rel:
            continue
        allowed = KNOWN_LEAKS.get(rel, set())
        for lineno, module in _escaping_imports(path):
            if module.startswith(ALLOWED_SDK):
                continue
            if any(module.startswith(a) for a in allowed):
                continue
            offenders.append(f"{rel}:{lineno} imports {module}")
    assert not offenders, (
        "A brand package reached outside the adapter SDK:\n  "
        + "\n  ".join(offenders)
        + "\n\nAn adapter translates VA's meaning into one provider's vocabulary; it does "
        "not consume VA's semantics. If you need a value, declare it in your own brand "
        "package the way adapters/roborock/vocabulary.py does. If you need a facility "
        "every adapter needs, it belongs in the SDK — add it to ALLOWED_SDK with the "
        "measurement that says so, in the same commit."
    )


def test_iso_2_the_known_leak_allowlist_is_shrink_only():
    """[ISO-2] A ledgered leak may be removed. It may not be joined."""
    live = {
        rel: {
            m
            for _, m in _escaping_imports(path)
            if not m.startswith(ALLOWED_SDK)
        }
        for rel, path in _brand_files()
        if "/" in rel
    }
    grown: list[str] = []
    for rel, ledgered in KNOWN_LEAKS.items():
        actual = live.get(rel, set())
        for extra in sorted(actual - ledgered):
            grown.append(f"{rel}: {extra}")
    assert not grown, (
        "New non-SDK imports in a file that already carries known debt:\n  "
        + "\n  ".join(grown)
        + "\n\nThe allowlist is SHRINK-ONLY. Fix the import, or remove an existing "
        "leak from the same file first."
    )


def test_iso_3_no_dynamic_import_escapes_the_static_check():
    """[ISO-3] importlib/__import__/sys.modules would make ISO-1 unenforceable."""
    offenders: list[str] = []
    for rel, path in _brand_files():
        src = open(path, encoding="utf-8").read()
        tree = ast.parse(src)
        for node in ast.walk(tree):
            if isinstance(node, ast.Call):
                fn = node.func
                name = getattr(fn, "id", None) or getattr(fn, "attr", None)
                if name in ("__import__", "import_module"):
                    offenders.append(f"{rel}:{node.lineno} calls {name}()")
            if isinstance(node, ast.Attribute) and node.attr == "modules":
                val = node.value
                if getattr(val, "id", None) == "sys":
                    offenders.append(f"{rel}:{node.lineno} touches sys.modules")
    assert not offenders, (
        "Dynamic import machinery inside an adapter:\n  "
        + "\n  ".join(offenders)
        + "\n\nISO-1 reads imports statically. A dynamic import is not a loophole to "
        "use, it is the loophole that makes the rule unenforceable."
    )


def test_iso_4_no_runtime_reach_into_a_passed_in_objects_privates():
    """[ISO-4] The reach an import graph cannot see.

    An adapter is handed `hass` and, in places, a manager. Touching `obj._private`
    on either is the same violation as importing the module it lives in, and it is
    invisible to every check above.
    """
    offenders: list[str] = []
    for rel, path in _brand_files():
        tree = ast.parse(open(path, encoding="utf-8").read())
        for node in ast.walk(tree):
            if not isinstance(node, ast.Attribute):
                continue
            if not node.attr.startswith("_") or node.attr.startswith("__"):
                continue
            recv = node.value
            name = getattr(recv, "id", None) or getattr(recv, "attr", None)
            # self/cls is the adapter's own state; a module-level private of the
            # brand's OWN package is equally fine.
            if name in (None, "self", "cls"):
                continue
            offenders.append(f"{rel}:{node.lineno} {name}.{node.attr}")
    assert not offenders, (
        "An adapter reached a private attribute on an object it was handed:\n  "
        + "\n  ".join(offenders)
        + "\n\nThis is the reach an import graph cannot see. If the value is part of "
        "the contract, expose it; if it is not, the adapter must not depend on it."
    )


def test_iso_5_the_detector_detects(tmp_path):
    """[ISO-5] The instrument, exercised against a leak built for the purpose.

    A gate only ever seen passing has not been tested — the lesson from the typeface
    baseline that was byte-identical to the default font for three days, and from a
    suite that stayed 935/935 green while a production property was renamed out from
    under it.

    This used to assert that a REAL ledgered leak (``eufy/adapter.py`` importing
    ``profiles.room_profiles``) was still found, and instructed whoever fixed it to
    delete the ledger entry and this test together. The leak was cut on 2026-08-07 when
    Eufy's vocabulary moved into ``adapters/eufy/room_profiles.py``, so the entry is
    gone. Deleting the self-test with it would have left the detector unexercised, which
    is the failure mode the test was written to prevent — so it now manufactures its own
    leak instead of borrowing one. The instrument stays proven with KNOWN_LEAKS empty,
    which is the state it should stay in.

    Fails two ways, both the point: a broken detector finds nothing, and a detector that
    flags EVERYTHING would also pass the positive half alone — hence the negative case.
    """
    leaky = tmp_path / "leaky_adapter.py"
    leaky.write_text(
        "from ...profiles.room_profiles import BUILT_IN_ROOM_PROFILES\n"
        "from ...core.capabilities import something\n",
        encoding="utf-8",
    )
    found = {m for _, m in _escaping_imports(str(leaky))}
    assert "profiles.room_profiles" in found, (
        "The detector no longer flags an escaping import. _escaping_imports has stopped "
        "seeing a relative import that reaches out of adapters/, so ISO-1 is green for "
        "the wrong reason."
    )

    clean = tmp_path / "clean_adapter.py"
    clean.write_text(
        "from .vocabulary import ROOM_PROFILES\n"
        "import logging\n",
        encoding="utf-8",
    )
    assert not {m for _, m in _escaping_imports(str(clean))}, (
        "The detector flags a purely LOCAL import as escaping — it would report every "
        "adapter, and ISO-1's silence would mean nothing."
    )


def _own_domain_hass_data_reads(path: str) -> list[tuple[int, str]]:
    """``hass.data[...]`` subscripts in one file naming VA's OWN domain.

    AST, not a text search: the only mentions of ``hass.data[DOMAIN]`` under adapters/
    today are DOCSTRINGS in registry.py explaining where the coordinator is stashed, and
    a grep-based fence would fail on prose describing the rule it enforces.

    Matches BOTH spellings in OWN_DOMAIN_KEYS — the imported constant and the string
    literal — because an adapter reaches the same bucket either way, and a fence that
    sees only one is a fence with a gate in it.
    """
    out: list[tuple[int, str]] = []
    tree = ast.parse(open(path, encoding="utf-8").read())
    for node in ast.walk(tree):
        if not isinstance(node, ast.Subscript):
            continue
        value = node.value
        if not (isinstance(value, ast.Attribute) and value.attr == "data"):
            continue
        key = node.slice
        name = (
            key.value if isinstance(key, ast.Constant)
            else key.id if isinstance(key, ast.Name)
            else None
        )
        if name in OWN_DOMAIN_KEYS:
            out.append((node.lineno, str(name)))
    return out


def test_iso_6_no_brand_file_reads_vas_own_hass_data():
    """[ISO-6] A brand package may reach any FOREIGN integration. Not ours.

    An adapter reading ``hass.data[DOMAIN]`` reads CORE runtime state from a brand file
    — the direction ISO-1 fences at the import graph, arriving instead through a dict at
    runtime where no import appears.

    ZERO SUBJECTS TODAY, deliberately. Which is why ISO-6b exists below: a fence with
    nothing to catch is indistinguishable from a broken one until the detector is
    exercised against a violation built for the purpose.
    """
    offenders = [
        (rel, line, key)
        for rel, abspath in _brand_files()
        for line, key in _own_domain_hass_data_reads(abspath)
    ]
    assert not offenders, (
        "a brand file reaches VA own-domain hass.data: "
        + "; ".join(f"{r}:{l} hass.data[{k}]" for r, l, k in offenders)
        + ". Reaching into robovac_mqtt or roborock is the adapter job; reaching into "
        "ours means core state is read from a brand package. Pass what the adapter "
        "needs as an argument instead."
    )


def test_iso_6b_the_own_domain_detector_detects(tmp_path):
    """[ISO-6b] The instrument, exercised — the same discipline as ISO-5.

    Fails two ways, both the point. A detector that finds nothing leaves ISO-6 green for
    the wrong reason; one that flags everything would also pass the positive half alone,
    so the negative case asserts a FOREIGN domain read is NOT reported.
    """
    leaky = tmp_path / "leaky_adapter.py"
    leaky.write_text(
        textwrap.dedent(
            """
            from ...const import DOMAIN

            def go(hass):
                a = hass.data[DOMAIN]["runtime"]
                b = hass.data["eufy_vacuum"]["adapter_coordinator"]
                return a, b
            """
        ),
        encoding="utf-8",
    )
    found = {key for _, key in _own_domain_hass_data_reads(str(leaky))}
    assert found == {"DOMAIN", "eufy_vacuum"}, (
        "the own-domain detector must catch BOTH spellings — the imported constant and "
        "the string literal — or a brand file reaches core state through whichever one "
        f"it misses and ISO-6 stays green. Found: {found}"
    )

    clean = tmp_path / "clean_adapter.py"
    clean.write_text(
        textwrap.dedent(
            """
            def go(hass):
                coords = hass.data["robovac_mqtt"][0]["coordinators"]
                parsed = hass.data["roborock"].get("maps")
                return coords, parsed
            """
        ),
        encoding="utf-8",
    )
    assert not _own_domain_hass_data_reads(str(clean)), (
        "the detector flagged a FOREIGN integration hass.data read. Reaching into "
        "robovac_mqtt and roborock is precisely what an adapter is FOR — a fence that "
        "blocks it would report every adapter and ISO-6 silence would mean nothing."
    )
