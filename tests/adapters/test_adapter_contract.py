"""Brand-agnostic adapter conformance suite.

These tests validate **any** registered adapter config against the framework's
documented contract — ``ADAPTER_CONFIG_SCHEMA`` in
``custom_components/eufy_vacuum/adapters/config_schema.py``. They are driven by
the ``adapter`` fixture (see ``conftest.py``), which is parametrized over every
brand in ``ADAPTER_BUILDERS``. Add a brand there and the whole suite runs
against it with no new test code.

The point of a *generic* harness: when a second brand lands (Roborock,
Dreame, …) its adapter config is held to exactly the same bar the framework
runtime, card, and config flow assume. The schema is the single source of
truth; this file is a machine-checkable reading of it.

Two layers:
  - A schema walker (``_validate``) that recursively checks a config against
    ``ADAPTER_CONFIG_SCHEMA``: required keys present, value types in the
    declared family, enum membership for ``values``, nested ``fields`` and
    catalog ``entry_fields`` required sub-keys.
  - Focused contract tests that assert the high-value invariants the runtime
    actually depends on (dispatch shape, entity-id format, registry validator
    agreement).
"""

from __future__ import annotations

import re
from typing import Any

import pytest

from custom_components.eufy_vacuum.adapters.config_schema import (
    ADAPTER_CONFIG_SCHEMA,
)
from custom_components.eufy_vacuum.adapters import registry


# A full HA entity id: "<domain>.<object_id>" — lowercase letters/underscores
# for the domain, lowercase alphanumerics/underscores for the object id.
_ENTITY_ID_RE = re.compile(r"^[a-z_]+\.[a-z0-9_]+$")


# ---------------------------------------------------------------------------
# Schema-string -> Python type-family mapping.
#
# Schema "type" strings describe a family, not an exact class. We map the
# outer container only — "list[str]" checks list-ness, not element types,
# since the schema's own entry_fields / nested rules cover element shape
# where it matters. A trailing "| null" (or "| None") permits None.
# Unrecognised type strings (e.g. "dict[str, Any]") fall back to the outer
# container so the walker never spuriously fails on an exotic annotation.
# ---------------------------------------------------------------------------

_TYPE_FAMILIES: dict[str, tuple[type, ...]] = {
    "str": (str,),
    "bool": (bool,),
    # bool is a subclass of int in Python; the schema's "int" fields are
    # never meant to accept True/False, so exclude bool explicitly below.
    "int": (int,),
    "float": (int, float),  # ints are acceptable where a float is declared
    "dict": (dict,),
    "list": (list,),
}


def _type_ok(value: Any, type_str: str) -> bool:
    """Return True if ``value`` matches the schema ``type_str`` family.

    Only the outer container is checked. "| null" / "| None" permits None.
    """
    allow_none = False
    spec = type_str.strip()
    for suffix in ("| null", "| none", "|null", "|none"):
        if spec.lower().endswith(suffix):
            allow_none = True
            spec = spec[: -len(suffix)].strip()
            break

    if value is None:
        return allow_none

    # Outer container family: take the text before any "[" generic args.
    outer = spec.split("[", 1)[0].strip()

    if outer == "int":
        # bool is a subclass of int — reject it for genuine int fields.
        return isinstance(value, int) and not isinstance(value, bool)
    if outer == "float":
        return isinstance(value, (int, float)) and not isinstance(value, bool)

    families = _TYPE_FAMILIES.get(outer)
    if families is None:
        # Unknown family ("Any", etc.) — don't fail the walk on it.
        return True
    return isinstance(value, families)


def _validate(config: Any, schema: dict[str, dict], path: str = "") -> list[str]:
    """Recursively validate ``config`` against a schema node.

    Returns a list of human-readable violation strings; empty == conformant.
    Walks: required keys, type families, enum ``values`` membership, nested
    ``fields`` (fixed sub-schema), and ``entry_fields`` (per-entry required
    sub-keys for catalog dicts/lists).
    """
    issues: list[str] = []

    if not isinstance(config, dict):
        return [f"{path or '<root>'}: expected dict, got {type(config).__name__}"]

    for key, spec in schema.items():
        loc = f"{path}.{key}" if path else key
        present = key in config

        if spec.get("required", False) and not present:
            issues.append(f"{loc}: required key missing")
            continue
        if not present:
            continue

        value = config[key]
        type_str = spec.get("type", "")

        if type_str and not _type_ok(value, type_str):
            issues.append(
                f"{loc}: expected type {type_str!r}, got {type(value).__name__}"
            )
            # Type is wrong — deeper checks would be noise.
            continue

        # Enum membership. For scalar fields value is the member; for list
        # fields every element must be a member.
        allowed = spec.get("values")
        if allowed is not None and value is not None:
            members = value if isinstance(value, list) else [value]
            for m in members:
                if m not in allowed:
                    issues.append(
                        f"{loc}: value {m!r} not in allowed {allowed}"
                    )

        # Nested fixed sub-schema.
        fields = spec.get("fields")
        if fields and isinstance(value, dict):
            issues.extend(_validate(value, fields, loc))

        # Catalog entry_fields: applies to each entry of a dict-of-dicts or
        # each element of a list-of-dicts.
        entry_fields = spec.get("entry_fields")
        if entry_fields:
            if isinstance(value, dict):
                entries = [(f"{loc}[{k!r}]", v) for k, v in value.items()]
            elif isinstance(value, list):
                entries = [(f"{loc}[{i}]", v) for i, v in enumerate(value)]
            else:
                entries = []
            for entry_loc, entry in entries:
                issues.extend(_validate(entry, entry_fields, entry_loc))

    return issues


# ---------------------------------------------------------------------------
# Sanity checks on the walker itself — so a green suite means the validator
# actually has teeth, not that it rubber-stamps everything.
# ---------------------------------------------------------------------------


class TestValidatorItself:
    def test_type_ok_basic_families(self):
        assert _type_ok("x", "str")
        assert _type_ok(3, "int")
        assert _type_ok(3.0, "float")
        assert _type_ok(3, "float")  # int acceptable where float declared
        assert _type_ok(True, "bool")
        assert _type_ok({}, "dict")
        assert _type_ok([], "list[str]")

    def test_type_ok_rejects_mismatch(self):
        assert not _type_ok("x", "int")
        assert not _type_ok(3, "str")
        assert not _type_ok([], "dict")

    def test_int_field_rejects_bool(self):
        # bool subclasses int — an int field must not silently accept True.
        assert not _type_ok(True, "int")
        assert not _type_ok(False, "float")

    def test_nullable_suffix(self):
        assert _type_ok(None, "str | null")
        assert _type_ok(None, "dict[str, Any] | null")
        assert not _type_ok(None, "str")
        assert _type_ok("x", "str | null")

    def test_validate_flags_missing_required(self):
        schema = {"a": {"type": "str", "required": True}}
        assert _validate({}, schema) == ["a: required key missing"]

    def test_validate_flags_bad_type(self):
        schema = {"a": {"type": "int", "required": True}}
        issues = _validate({"a": "nope"}, schema)
        assert issues and "expected type 'int'" in issues[0]

    def test_validate_flags_bad_enum(self):
        schema = {"a": {"type": "str", "values": ["x", "y"]}}
        issues = _validate({"a": "z"}, schema)
        assert issues and "not in allowed" in issues[0]

    def test_validate_recurses_entry_fields(self):
        schema = {
            "cat": {
                "type": "dict[str, dict]",
                "entry_fields": {"v": {"type": "str", "required": True}},
            }
        }
        issues = _validate({"cat": {"k1": {}}}, schema)
        assert issues == ["cat['k1'].v: required key missing"]


# ---------------------------------------------------------------------------
# Generic contract tests — run once per registered brand via the `adapter`
# fixture (brand_name, config).
# ---------------------------------------------------------------------------


class TestAdapterContract:
    def test_produces_config_dict(self, adapter):
        name, config = adapter
        assert isinstance(config, dict), f"{name}: adapter produced no dict"
        assert config, f"{name}: adapter produced an empty config"

    def test_required_top_level_keys(self, adapter):
        name, config = adapter
        required = [
            k for k, spec in ADAPTER_CONFIG_SCHEMA.items()
            if spec.get("required", False)
        ]
        missing = [k for k in required if k not in config]
        assert not missing, f"{name}: missing required top-level keys: {missing}"

    def test_schema_conformance(self, adapter):
        name, config = adapter
        issues = _validate(config, ADAPTER_CONFIG_SCHEMA)
        assert not issues, (
            f"{name}: adapter config violates ADAPTER_CONFIG_SCHEMA:\n"
            + "\n".join(f"  - {i}" for i in issues)
        )

    def test_registry_validate_clean(self, adapter):
        """The framework's own runtime validator must accept the config."""
        name, config = adapter
        issues = registry._validate_adapter(config)
        assert issues == [], f"{name}: registry rejected config: {issues}"

    def test_source_is_valid_enum(self, adapter):
        name, config = adapter
        allowed = ADAPTER_CONFIG_SCHEMA["source"]["values"]
        assert config.get("source") in allowed, (
            f"{name}: source {config.get('source')!r} not in {allowed}"
        )

    def test_adapter_id_nonempty(self, adapter):
        name, config = adapter
        adapter_id = config.get("adapter_id")
        assert isinstance(adapter_id, str) and adapter_id.strip(), (
            f"{name}: adapter_id must be a non-empty string"
        )

    # --- dispatch (required block, the runtime depends on its shape) -------

    def test_dispatch_contract(self, adapter):
        name, config = adapter
        dispatch = config.get("dispatch")
        assert isinstance(dispatch, dict), f"{name}: dispatch must be a dict"

        template = dispatch.get("template")
        allowed = ADAPTER_CONFIG_SCHEMA["dispatch"]["fields"]["template"]["values"]
        assert template in allowed, (
            f"{name}: dispatch.template {template!r} not in {allowed}"
        )

        assert isinstance(dispatch.get("service_domain"), str) and \
            dispatch["service_domain"], f"{name}: dispatch.service_domain missing"
        assert isinstance(dispatch.get("service_name"), str) and \
            dispatch["service_name"], f"{name}: dispatch.service_name missing"

    # --- entities ----------------------------------------------------------

    def test_entities_block_present(self, adapter):
        name, config = adapter
        entities = config.get("entities")
        assert isinstance(entities, dict), f"{name}: entities must be a dict"

    def test_entity_values_are_entity_ids(self, adapter):
        """Every declared entity value must look like a full HA entity id."""
        name, config = adapter
        entities = config.get("entities", {})
        bad = {
            k: v for k, v in entities.items()
            if v is not None and not (
                isinstance(v, str) and _ENTITY_ID_RE.match(v)
            )
        }
        assert not bad, f"{name}: malformed entity ids: {bad}"

    # --- vocabulary option lists (card dropdowns) --------------------------

    def test_vocabulary_option_lists_well_formed(self, adapter):
        """Each {value,label} option list has non-empty string value+label."""
        name, config = adapter
        vocab = config.get("vocabulary", {})
        option_keys = [
            "clean_mode_options",
            "fan_speed_options",
            "water_level_options",
            "clean_intensity_options",
        ]
        for key in option_keys:
            options = vocab.get(key)
            if options is None:
                continue
            assert isinstance(options, list), f"{name}: {key} must be a list"
            for i, opt in enumerate(options):
                assert isinstance(opt, dict), f"{name}: {key}[{i}] not a dict"
                for sub in ("value", "label"):
                    val = opt.get(sub)
                    assert isinstance(val, str) and val != "", (
                        f"{name}: {key}[{i}].{sub} must be a non-empty string"
                    )

    # --- catalog entry_fields (maintenance, water) -------------------------

    def test_maintenance_components_entry_fields(self, adapter):
        name, config = adapter
        components = config.get("maintenance_components")
        if not components:
            pytest.skip(f"{name}: no maintenance_components declared")
        required = [
            k for k, spec in ADAPTER_CONFIG_SCHEMA["maintenance_components"][
                "entry_fields"
            ].items()
            if spec.get("required", False)
        ]
        for comp_id, comp in components.items():
            missing = [k for k in required if k not in comp]
            assert not missing, (
                f"{name}: maintenance component {comp_id!r} missing {missing}"
            )

    def test_water_model_configs_entry_fields(self, adapter):
        name, config = adapter
        models = config.get("water_model_configs")
        if not models:
            pytest.skip(f"{name}: no water_model_configs declared")
        for model_code, cfg in models.items():
            assert "robot_internal_tank_ml" in cfg, (
                f"{name}: water model {model_code!r} missing robot_internal_tank_ml"
            )
            assert isinstance(cfg["robot_internal_tank_ml"], (int, float)), (
                f"{name}: water model {model_code!r} robot_internal_tank_ml "
                f"must be numeric"
            )
