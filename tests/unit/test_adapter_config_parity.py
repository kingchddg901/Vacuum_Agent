"""ADAPTER_CONFIG_SCHEMA parity: the schema is a FLOOR, not the contract.

Two things add requirements the schema does not express, and both produced a live
defect found on 2026-08-15 by a generator that trusted the schema as the whole
truth:

  1. registry._validate_adapter HAND-ENFORCES keys the schema calls optional.
     ``room_profiles`` was ``required: False`` in the schema while
     ``_validate_room_profiles`` (registry.py) rejected its absence outright. Only
     the CONFIG path was bitten: ``validate_adapter_config()`` -- the
     ``save_adapter_config`` service -- honoured the flag and SAVED HAPPILY, then
     registration refused the stored config. That lands the failure exactly where
     registry's own docstring says it must not ("fails here rather than at the
     first clean"). Code adapters never noticed: they bypass the schema walk.

  2. Code READS keys the schema never declares, while doc 22 documents them.
     ``low_clean_water_margin_ml`` is read at ``planning/run_plan.py:539`` and
     documented in doc 22 with a worked example -- and was absent from
     ``water_model_configs.entry_fields``. ``entry_fields`` IS enforced
     (``validate_against_schema`` recurses into it, unknown-key rejection
     included), so a porter following the doc wrote that key, hit save, and got
     "key(s) not declared in the schema". Our own adapters never hit it.

Both are the same shape: THE SCHEMA IS NOT THE ONLY AUTHORITY, and nothing was
checking that the authorities agree. Sibling gate:
``tests/unit/test_service_declaration_parity.py`` does this for the service
surface; this is the adapter-config equivalent.

WHAT THIS DELIBERATELY DOES NOT CHECK. "Every key the code reads is declared" was
measured before it was designed: scanning ``.get("literal")`` on receivers named
config/cfg/model_config yields 141 distinct keys of which 61 are not in the
schema -- and nearly all 61 are ROOM config, estimator internals or map-source
sub-dicts, not adapter config. A gate needing a 61-entry allowlist is where real
findings go to hide, so it is not built. Doc 22's field tables are the tractable
proxy and they caught the real one.

Run: docker pytest tests/unit/test_adapter_config_parity.py --no-cov
"""

from __future__ import annotations

import ast
import re
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
COMPONENT = REPO_ROOT / "custom_components" / "eufy_vacuum"
SCHEMA_PY = COMPONENT / "adapters" / "config_schema.py"
REGISTRY_PY = COMPONENT / "adapters" / "registry.py"
# The hand-written config reference was retired 2026-08-23; its successor is
# GENERATED from ADAPTER_CONFIG_SCHEMA itself. Same row shape, so this check keeps
# running — and what it now catches is a GENERATOR bug: a field emitted into the
# porter-facing table that the schema does not actually declare.
DOC_22 = (
    REPO_ROOT / ".claude" / "generated-docs" / "adapter-config"
    / "ADAPTER-CONFIG.generated.md"
)

# Schema metadata keys — the vocabulary OF the schema, never config keys.
_META = {
    "type", "required", "description", "entry_fields", "fields",
    "values", "default", "example", "note",
}

# ---------------------------------------------------------------------------
# SCHEMA_ABSENT_BY_DESIGN -- doc 22 documents these, the schema deliberately does
# not declare them. Each needs the REASON, not just the name: an allowlist whose
# entries say only "known" cannot be re-reviewed by the next reader.
# ---------------------------------------------------------------------------
SCHEMA_ABSENT_BY_DESIGN: dict[str, str] = {
    "default": (
        "NOT a top-level config field. It is a nested entry-field key inside a parent "
        "block's own '**Fields**' sub-table in the generated reference "
        "(e.g. wash_frequency_bounds' default/min/max). The row regex matches any "
        "`key` | `type` | yes/no row and cannot see nesting, so a nested key reads as "
        "a top-level one. Widening the regex to understand nesting would couple this "
        "test to the generator's heading layout; exempting the name is the cheaper "
        "and more stable answer."
    ),
}

# REMOVED 2026-08-23: "remaining_is_state". The allowlist rotted and the rot test
# caught it. The key was PRUNED from adapters/roborock/maintenance_components.py --
# four components declared it and nothing read it -- so the generated reference no
# longer documents it and the exemption had nothing left to exempt.


def _load_schema_dict() -> ast.Dict:
    """The ADAPTER_CONFIG_SCHEMA literal.

    It is written ``ADAPTER_CONFIG_SCHEMA: dict[str, dict] = {...}`` — an
    ast.AnnAssign, NOT an ast.Assign. Matching only Assign silently finds nothing
    and every assertion below then passes over an empty set. That exact mistake
    was made three separate times on 2026-08-15, which is why the "measured
    something" guards exist.
    """
    tree = ast.parse(SCHEMA_PY.read_text(encoding="utf-8"))
    for node in ast.walk(tree):
        target = (
            node.target if isinstance(node, ast.AnnAssign)
            else node.targets[0] if isinstance(node, ast.Assign) and len(node.targets) == 1
            else None
        )
        if (isinstance(target, ast.Name)
                and target.id == "ADAPTER_CONFIG_SCHEMA"
                and isinstance(node.value, ast.Dict)):
            return node.value
    raise AssertionError("ADAPTER_CONFIG_SCHEMA literal not found — gate is broken")


def _top_level_specs() -> dict[str, dict]:
    """{top-level key: {'required': bool}} — only the outermost block."""
    out: dict[str, dict] = {}
    schema = _load_schema_dict()
    for key, spec in zip(schema.keys, schema.values):
        if not (isinstance(key, ast.Constant) and isinstance(key.value, str)):
            continue
        required = False
        if isinstance(spec, ast.Dict):
            for k, v in zip(spec.keys, spec.values):
                if getattr(k, "value", None) == "required" and isinstance(v, ast.Constant):
                    required = bool(v.value)
        out[key.value] = {"required": required}
    return out


def _all_schema_keys() -> set[str]:
    """Every config key the schema declares, at any depth (metadata excluded)."""
    found: set[str] = set()

    def walk(d: ast.Dict) -> None:
        for k, v in zip(d.keys, d.values):
            if isinstance(k, ast.Constant) and isinstance(k.value, str) and k.value not in _META:
                found.add(k.value)
            if isinstance(v, ast.Dict):
                walk(v)

    walk(_load_schema_dict())
    return found


def _hand_enforced_required_keys() -> set[str]:
    """Keys registry.py rejects the ABSENCE of, inside a validate* function.

    Matches ``if "X" not in config:`` — a required-key guard. Enum-membership
    checks (``engine_name not in known_engine_names()``) are a different thing and
    are excluded by requiring a string-literal left operand.
    """
    tree = ast.parse(REGISTRY_PY.read_text(encoding="utf-8"))
    keys: set[str] = set()
    for fn in ast.walk(tree):
        if not (isinstance(fn, ast.FunctionDef) and "validate" in fn.name):
            continue
        for cmp_node in ast.walk(fn):
            if not (isinstance(cmp_node, ast.Compare) and cmp_node.ops
                    and isinstance(cmp_node.ops[0], ast.NotIn)):
                continue
            left = cmp_node.left
            if isinstance(left, ast.Constant) and isinstance(left.value, str):
                keys.add(left.value)
    return keys


# doc 22 field-table row:  | `key` | `type` | yes/no | description
_DOC_ROW = re.compile(
    r"^\|\s*`([a-z_][a-z0-9_]*)`\s*\|\s*`?[^|`]*`?\s*\|\s*(?:yes|no)\s*\|",
    re.M | re.I,
)


def _documented_field_keys() -> set[str]:
    return set(_DOC_ROW.findall(DOC_22.read_text(encoding="utf-8")))


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------

def test_hand_enforced_keys_are_required_in_the_schema():
    """A key registration rejects the absence of must not read `required: False`.

    Otherwise the save path accepts a config the register path will refuse, and
    the porter learns about it at the wrong moment. This is the `room_profiles`
    defect, generalised.
    """
    enforced = _hand_enforced_required_keys()
    specs = _top_level_specs()

    assert enforced, (
        "found ZERO hand-enforced required keys in registry.py — the AST scan is "
        "broken (it found some on 2026-08-15), so this assertion proves nothing"
    )

    wrong = [
        k for k in sorted(enforced)
        if k in specs and not specs[k]["required"]
    ]
    assert not wrong, (
        "registry._validate_adapter rejects these configs for lacking a key that "
        "ADAPTER_CONFIG_SCHEMA marks optional — so validate_adapter_config() saves "
        f"a config that can never register: {wrong}"
    )


def test_documented_config_fields_exist_in_the_schema():
    """Doc 22 must not document a config key the schema will reject on save.

    `entry_fields` is enforced with unknown-key rejection, so a documented-but-
    undeclared key is not a doc nit — following the doc produces a config that
    fails validation. This is the `low_clean_water_margin_ml` defect.
    """
    documented = _documented_field_keys()
    declared = _all_schema_keys()

    assert len(documented) >= 20, (
        f"parsed only {len(documented)} field rows out of doc 22 — the table regex "
        "has drifted from the document's format, so this assertion is checking "
        "almost nothing (it parsed 28 on 2026-08-15)"
    )
    assert len(declared) >= 100, (
        f"walked only {len(declared)} schema keys — the schema walk is broken "
        "(it found 182 on 2026-08-15)"
    )

    missing = sorted(documented - declared - set(SCHEMA_ABSENT_BY_DESIGN))
    assert not missing, (
        "doc 22 documents these as config fields but ADAPTER_CONFIG_SCHEMA does not "
        "declare them, so a config carrying one is rejected as 'key(s) not declared "
        f"in the schema': {missing}\n"
        "Either declare them, or add them to SCHEMA_ABSENT_BY_DESIGN with the reason."
    )


def test_schema_absent_allowlist_does_not_rot():
    """An allowlisted key that IS now declared must leave the list.

    Otherwise it masks the day someone removes the declaration again — the same
    reverse-check `test_expected_failures_do_not_rot` carries for the service gate.
    """
    declared = _all_schema_keys()
    documented = _documented_field_keys()

    now_declared = sorted(k for k in SCHEMA_ABSENT_BY_DESIGN if k in declared)
    assert not now_declared, (
        "SCHEMA_ABSENT_BY_DESIGN entries that the schema now declares — remove them: "
        f"{now_declared}"
    )

    undocumented = sorted(k for k in SCHEMA_ABSENT_BY_DESIGN if k not in documented)
    assert not undocumented, (
        "SCHEMA_ABSENT_BY_DESIGN entries doc 22 no longer documents in a field table "
        f"— the exemption has nothing left to exempt, remove them: {undocumented}"
    )
