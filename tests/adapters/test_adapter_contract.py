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
    _type_ok,
    validate_adapter_config,
    validate_against_schema as _validate,
)
from custom_components.eufy_vacuum.adapters import registry


# A full HA entity id: "<domain>.<object_id>" — lowercase letters/underscores
# for the domain, lowercase alphanumerics/underscores for the object id.
_ENTITY_ID_RE = re.compile(r"^[a-z_]+\.[a-z0-9_]+$")


# ---------------------------------------------------------------------------
# RP-033/RF-32: the schema walker (type-family mapping, ``_type_ok``,
# ``_validate``) used to live here as pytest-only code -- ADAPTER_CONFIG_SCHEMA
# was a documented contract nothing at runtime actually enforced. It is now
# extracted to config_schema.py (``validate_against_schema`` / aliased ``_validate``
# above, plus ``validate_adapter_config``) so this test suite and the real
# save-path (services/adapter_config.py) share ONE implementation of the walk
# instead of two that can drift apart. Imported, not redefined.
# ---------------------------------------------------------------------------


# ---------------------------------------------------------------------------
# Sanity checks on the walker itself — so a green suite means the validator
# actually has teeth, not that it rubber-stamps everything.
# ---------------------------------------------------------------------------


class TestValidatorItself:
    def test_an_undeclared_key_is_caught_at_every_level(self):
        """[RC-1] The walker iterates the SCHEMA, so an unknown key was never inspected.

        A verifier proved this by running it: a config carrying a typo'd top-level block
        AND a made-up nested key produced output IDENTICAL to the clean config. That is
        why the artifact called "the contract, as data" could sit blocks behind what
        actually shipped without one test going red.

        Adding the check immediately found three real undeclared keys in SHIPPED configs
        (`dispatch.global_pre_calls[].mixed_mode_water_policy`,
        `water_model_configs[].water_rates`, and the dead `remaining_is_state`), so this
        is not only a tripwire for brand 3.
        """
        schema = {
            "known": {"type": "str", "required": False},
            "block": {
                "type": "dict",
                "required": False,
                "fields": {"inner": {"type": "str", "required": False}},
            },
        }
        assert _validate({"known": "x"}, schema) == []

        top = _validate({"known": "x", "typoo": 1}, schema)
        assert len(top) == 1 and "typoo" in top[0]

        # Nested too — a typo inside a block the schema DOES enumerate.
        nested = _validate({"block": {"inner": "x", "inr": "y"}}, schema)
        assert len(nested) == 1 and "inr" in nested[0] and "block" in nested[0]

    def test_open_ended_blocks_are_not_flagged(self):
        """[RC-1] Nine schema blocks are declared as bare `dict` with no `fields`
        (settings_selects, mapping, map_render, room_profiles, …) and are legitimately
        open-ended. Asserting unknown keys inside those would be noise, not a contract —
        so the check only applies where the schema actually enumerates the shape."""
        schema = {"opaque": {"type": "dict", "required": False}}
        assert _validate({"opaque": {"anything": 1, "at": "all"}}, schema) == []

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
        # Uses the production entry point directly (not the generic _validate
        # alias) — this is the exact function services/adapter_config.py calls
        # before persisting/registering a stored config.
        issues = validate_adapter_config(config)
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


def test_no_undeclared_top_level_keys(adapter):
    """[AC-schema] Every top-level key a brand ships MUST be declared in
    ADAPTER_CONFIG_SCHEMA.

    The schema walker (_validate) iterates schema.items(), so it is structurally blind to
    a config key the schema does not declare: a whole block can ship, be load-bearing at
    runtime, and never be validated or documented. This assertion is the inverse direction
    and is what makes a future schema-absent block a RED test instead of a silent gap.

    A leading-underscore key is exempt: RP-033/VAC-3 stashes adapter-internal bookkeeping
    (the code adapters' full entity_candidates, read back by
    core/manager.refresh_vacuum_capabilities) under such a key -- deliberately NOT part of
    the user-facing schema surface a stored/config adapter would ever declare.
    """
    name, config = adapter
    undeclared = sorted(
        k for k in (set(config) - set(ADAPTER_CONFIG_SCHEMA))
        if not (isinstance(k, str) and k.startswith("_"))
    )
    assert not undeclared, (
        f"{name}: top-level keys shipped but NOT declared in ADAPTER_CONFIG_SCHEMA: "
        f"{undeclared}. Declare them in config_schema.py (the schema is the contract) "
        f"or stop shipping them."
    )


def _undeclared_nested(config: Any, schema: dict[str, Any], path: str = "") -> list[str]:
    """Return dotted paths of config keys not declared under a schema ``fields`` block.

    Descends ONLY where the schema declares ``fields``. A block with no ``fields`` is
    opaque BY DECLARATION (several engine blocks are validated at registration instead),
    so its interior is deliberately not policed here — that keeps this check precise
    rather than noisy.
    """
    out: list[str] = []
    if not isinstance(config, dict):
        return out
    for key, spec in schema.items():
        if key not in config or not isinstance(spec, dict):
            continue
        fields = spec.get("fields")
        if not isinstance(fields, dict):
            continue
        value = config[key]
        if not isinstance(value, dict):
            continue
        loc = f"{path}.{key}" if path else key
        out.extend(
            f"{loc}.{k}" for k in sorted(set(value) - set(fields))
            if not (isinstance(k, str) and k.startswith("_"))
        )
        out.extend(_undeclared_nested(value, fields, loc))
    return out


def test_no_undeclared_nested_keys(adapter):
    """[AC-schema-nested] A key inside a declared ``fields`` block must itself be declared.

    Same blind spot as the top-level case, one level down: the walker checks the fields it
    knows about and never notices an extra one. Only blocks that declare ``fields`` are
    descended into, so deliberately-opaque blocks stay opaque.
    """
    name, config = adapter
    undeclared = _undeclared_nested(config, ADAPTER_CONFIG_SCHEMA)
    assert not undeclared, (
        f"{name}: nested keys shipped but NOT declared in ADAPTER_CONFIG_SCHEMA: "
        f"{undeclared}. Declare them under the parent's 'fields' or stop shipping them."
    )


# --- new-room defaults must be the brand's OWN vocabulary --------------------
#
# The tripwire for RC-6/RB-1. Room creation used to hardcode Eufy display literals
# ("Max"/"Off"/"Quick") with no way to consult the adapter at all, so every Roborock room
# was created with settings its own brand does not recognise. These run for every entry in
# ADAPTER_BUILDERS, so a THIRD brand that forgets to declare room_profiles goes red here
# rather than shipping silently with Eufy vocabulary in its rooms.

def _option_values(config, key):
    """Declared card dropdown values for one axis, or None when the brand omits the axis.

    The option lists live under ``vocabulary`` (both brands declare them there), alongside
    the state-vocabulary sets.
    """
    options = (config.get("vocabulary") or {}).get(key)
    if not isinstance(options, list) or not options:
        return None
    return {str(o.get("value")) for o in options if isinstance(o, dict)}


def test_new_room_defaults_use_only_this_brands_declared_vocabulary(adapter):
    """A new room's settings must be selectable in this brand's own option lists.

    This is the assertion that would have caught the shipped bug: a Roborock room created
    with fan_speed "Max" is not in FAN_SPEED_OPTIONS (whose values are lowercase), so the
    card's strict-equality chip row showed nothing selected and the per_room_live_settings
    options_key filter dropped the value entirely — no suction applied at all.
    """
    from custom_components.eufy_vacuum.rooms.room_defaults import (
        resolve_new_room_defaults,
    )

    brand, config = adapter
    defaults = resolve_new_room_defaults(config.get("room_profiles"))

    for field, options_key in (
        ("fan_speed", "fan_speed_options"),
        ("water_level", "water_level_options"),
        ("clean_mode", "clean_mode_options"),
        ("clean_intensity", "clean_intensity_options"),
    ):
        declared = _option_values(config, options_key)
        value = defaults.get(field)

        if declared is None:
            # A brand that exposes no such axis must not have a default for it either —
            # Roborock declares no clean_intensity_options, so storing "Quick" on every
            # one of its rooms would be an inert field nobody can act on.
            assert not value, (
                f"{brand}: declares no {options_key} but a new room would store "
                f"{field}={value!r}"
            )
            continue

        # An axis the brand DOES expose may still be left to the room/profile; but if the
        # default profile names a value, it has to be one the user could have picked.
        if value:
            assert value in declared, (
                f"{brand}: a new room would get {field}={value!r}, which is not in its "
                f"declared {options_key} {sorted(declared)}"
            )


def test_new_room_default_profile_exists_in_this_brands_catalog(adapter):
    """default_profile must name a profile the brand actually declares.

    Cheap, and it is the failure a brand-3 port makes first: declare builtins, forget to
    point default_profile at one of them (or point it at a key from the Eufy catalog that
    the brand's own builtins do not define).
    """
    from custom_components.eufy_vacuum.profiles.room_profiles import (
        resolve_profile_catalog,
    )

    brand, config = adapter
    catalog = resolve_profile_catalog(config.get("room_profiles"))

    name = catalog.get("default_profile")
    builtins = catalog.get("builtins")
    assert isinstance(builtins, dict) and builtins, f"{brand}: no builtins resolved"
    assert name in builtins, (
        f"{brand}: default_profile {name!r} is not among its builtins "
        f"{sorted(builtins)}"
    )


def test_floor_type_defaults_use_only_this_brands_declared_vocabulary(adapter):
    """The carpet/hard-floor overrides are applied to EVERY room, not just new ones.

    resolve_room_profile_for_room reads the carpet entry as this brand's no-water value,
    so a Eufy-cased "Off" sitting in a Roborock catalog is not cosmetic — it is written
    onto the resolved settings of every carpet room.
    """
    from custom_components.eufy_vacuum.profiles.room_profiles import (
        resolve_profile_catalog,
    )

    brand, config = adapter
    catalog = resolve_profile_catalog(config.get("room_profiles"))

    for catalog_key, options_key in (
        ("floor_type_water_defaults", "water_level_options"),
        ("floor_type_fan_defaults", "fan_speed_options"),
    ):
        declared = _option_values(config, options_key)
        if declared is None:
            continue
        for floor_type, value in (catalog.get(catalog_key) or {}).items():
            assert str(value) in declared, (
                f"{brand}: {catalog_key}[{floor_type}] = {value!r} is not in its declared "
                f"{options_key} {sorted(declared)}"
            )


def test_a_declared_live_pose_names_a_backend_core_can_read(adapter):
    """A pose block core cannot dispatch on is a pose nobody receives.

    THE DEFECT, GENERALISED. ``async_get_map_live_pose`` used to BE the eufy-clean reader,
    so it keyed off this block merely EXISTING. Roborock's position was live on its parsed
    map the whole time and that accessor answered ``not_configured`` — the stall capture
    drew rooms with no robot in them, and the pose ring recorded no anchors, because a
    declaration was missing rather than a capability.

    Naming the backend is what makes that failure loud: an unreadable declaration is now a
    red test here instead of a brand silently reported as having no position. Runs against
    every brand in ADAPTER_BUILDERS, so the next adapter cannot repeat it.
    """
    from custom_components.eufy_vacuum.mapping.map_source_coordinator import (
        POSE_BACKEND_INMEM_PIXELS,
        POSE_BACKEND_PARSED_MAPDATA,
    )

    brand, config = adapter
    source = config.get("map_state_source")
    if not isinstance(source, dict):
        pytest.skip(f"{brand} declares no map_state_source")
    live_pose = source.get("live_pose")
    if not isinstance(live_pose, dict):
        pytest.skip(f"{brand} declares no live_pose")

    known = {POSE_BACKEND_INMEM_PIXELS, POSE_BACKEND_PARSED_MAPDATA}
    backend = live_pose.get("backend")

    assert backend in known, (
        f"{brand}: live_pose.backend = {backend!r} is not one core can read {sorted(known)} "
        "— every consumer of async_get_map_live_pose would get an absent marker"
    )


def test_a_declared_live_pose_declares_its_cadence(adapter):
    """The pose cadence sizes the stall capture's trail window and picks its draw style.

    Undeclared, the capture falls back to the historical ±30 s and a connected line — which
    is right for a fast brand and wrong for a slow one, where it collects two samples and
    would join half a minute of unobserved travel into a straight segment. A brand that can
    say how often its position changes must say it.
    """
    brand, config = adapter
    source = config.get("map_state_source")
    if not isinstance(source, dict):
        pytest.skip(f"{brand} declares no map_state_source")
    live_pose = source.get("live_pose")
    if not isinstance(live_pose, dict):
        pytest.skip(f"{brand} declares no live_pose")

    refresh = live_pose.get("pose_refresh_s")

    assert isinstance(refresh, (int, float)) and not isinstance(refresh, bool), (
        f"{brand}: live_pose.pose_refresh_s = {refresh!r} is not a number"
    )
    assert refresh > 0, f"{brand}: a pose cadence of {refresh} is not a cadence"


def test_every_brand_registrar_arms_the_exclusivity_guard():
    """EVERY brand must hand core its suffix vocabulary — not just the one we
    happened to write the guard for.

    live:ENT-4 excludes a LONGER declared suffix from a shorter one's sibling
    match: `_cleaning_area` also matches `..._total_cleaning_area`, so without
    the full vocabulary a per-run metric can bind to the LIFETIME TOTAL. That is
    the 17,975 ft² bug, and it feeds the learning store, run segmentation and
    battery metrics while never raising.

    The guard shipped armed on Eufy and UNARMED on Roborock for an entire
    release. The pin test that was supposed to prevent exactly this
    (tests/adapters/eufy/test_suffix_vocabulary.py) is brand-scoped by
    construction — its own docstring says "a correct core rule with NO CALLER is
    precisely the reachability gap behind issue #49 ... Audit the call site, not
    just the function", and it audits one call site. A per-brand guarantee reads
    as a framework guarantee, which is the shape this project keeps paying for.

    Parametrised over BRAND_REGISTRARS so a NEW brand cannot ship unarmed: the
    registrar table is the switch that makes a brand reachable, so anything in
    it is answerable to this.

    Source-level for the same reason the Eufy original is: standing up a full
    registration would pass whether or not the kwarg survives, because nothing
    downstream asserts on it.
    """
    import ast
    import inspect
    import textwrap

    from custom_components.eufy_vacuum.adapters.brands import BRAND_REGISTRARS

    assert BRAND_REGISTRARS, "no brands registered — this test is anchored wrong"

    unarmed: list[str] = []
    checked = 0
    for registrar in BRAND_REGISTRARS:
        source = textwrap.dedent(inspect.getsource(registrar.register))
        # Parsed, not substring-matched. The first version of this test asked
        # whether "reserved_suffixes=" appeared ANYWHERE in the function, and a
        # deliberate ablation that stripped it from the detect_capabilities call
        # still passed — because the adapter hands the same vocabulary to
        # resolve_declared_entities a few lines later. A guard that reads the
        # right token in the wrong call is the failure it exists to catch.
        calls = [
            node
            for node in ast.walk(ast.parse(source))
            if isinstance(node, ast.Call)
            and getattr(node.func, "id", getattr(node.func, "attr", None))
            == "detect_capabilities"
        ]
        if not calls:
            # A brand that does not detect capabilities has no guard to arm.
            continue
        checked += 1
        for call in calls:
            if not any(kw.arg == "reserved_suffixes" for kw in call.keywords):
                unarmed.append(registrar.brand_id)

    assert checked, (
        "no brand registrar calls detect_capabilities — this test is anchored to "
        "the wrong function and is asserting nothing"
    )

    assert not unarmed, (
        f"brand(s) {unarmed} call detect_capabilities without reserved_suffixes, "
        "so the live:ENT-4 exclusivity guard is unarmed for them: a per-run role "
        "can silently bind to a lifetime counter on that hardware"
    )


def test_every_brand_vocabulary_declares_both_halves_of_the_known_collision():
    """A vocabulary is only protective if it CONTAINS the colliding partner.

    Passing `reserved_suffixes` is necessary but not sufficient: the guard
    excludes a longer declared suffix, so if a brand declares `_cleaning_area`
    and never declares `_total_cleaning_area`, the longer name is not in the
    universe and the shorter one claims it anyway. Roborock shipped in exactly
    that state — `_total_cleaning_count` was declared but not the `_area` /
    `_time` halves that actually collide — while carrying all three entities on
    real hardware.

    Checked as a PAIRING rule rather than a fixed list, so it keeps meaning
    something for a brand with different names: for every `_total_<x>` a brand
    declares we do not care, but for every per-run suffix that has a `_total_`
    partner ON THE SAME BRAND, both must be known.
    """
    import importlib

    from custom_components.eufy_vacuum.adapters.brands import BRAND_REGISTRARS

    missing: list[str] = []
    for registrar in BRAND_REGISTRARS:
        module_root = registrar.register.__module__.rsplit(".", 1)[0]
        try:
            entities = importlib.import_module(f"{module_root}.entities")
        except ModuleNotFoundError:  # pragma: no cover - brand without a vocabulary module
            continue
        suffixes = {
            value
            for name, value in vars(entities).items()
            if name.startswith("SUFFIX_") and isinstance(value, str) and value
        }
        for suffix in sorted(suffixes):
            if suffix.startswith("_total_"):
                continue
            partner = f"_total{suffix}"
            # Only demand the partner when the brand shows it knows the family —
            # i.e. it declares at least one `_total_*` suffix at all.
            if not any(s.startswith("_total_") for s in suffixes):
                continue
            if partner in suffixes:
                continue
            if suffix in ("_cleaning_area", "_cleaning_time"):
                missing.append(f"{registrar.brand_id}:{suffix} (needs {partner})")

    assert not missing, (
        "brand vocabulary is missing the lifetime half of a known collision, so "
        "the exclusivity guard cannot exclude it: " + ", ".join(missing)
    )


# ---------------------------------------------------------------------------
# D17 - `blocked_task_status_states` is SUPERSEDED, and that claim needs a bite
# ---------------------------------------------------------------------------


def test_d17_the_dead_block_key_is_fully_covered_by_the_live_gate():
    """The schema and doc 22 §5 now tell a porter that `blocked_task_status_states` is
    dead because the gate it named is spelled with different vocabulary, and point them
    at `active_run_task_states` / `hard_service_states` instead.

    That is a CLAIM about the live code, and without this it rots silently: drop
    "washing mop" from HARD_SERVICE_STATES and the documentation becomes false while
    every test stays green — a start during a mop wash would no longer be refused, and
    the surface a porter reads would still say it is.

    RED IF ANY DECLARED VALUE STOPS BEING COVERED. The point is the equivalence, not the
    contents of either set, so both sides are read from the real vocabulary rather than
    retyped.
    """
    from custom_components.eufy_vacuum.adapters.eufy.vocabulary import (
        ACTIVE_RUN_TASK_STATES,
        HARD_SERVICE_STATES,
    )
    from custom_components.eufy_vacuum.jobs.job_monitor import _norm

    declared = ["Cleaning", "Returning", "Washing Mop"]
    live_gate = set(ACTIVE_RUN_TASK_STATES) | set(HARD_SERVICE_STATES)

    uncovered = [value for value in declared if _norm(value) not in live_gate]
    assert not uncovered, (
        "blocked_task_status_states is documented as superseded by the live start gate, "
        "but these declared values are no longer refused by it: "
        + ", ".join(repr(v) for v in uncovered)
        + " — either restore the coverage, or correct adapters/config_schema.py and "
        "docs/dev/22-adapter-contract.md §5, which currently tell a porter it is safe "
        "to ignore this key."
    )


def test_d17_the_declared_values_still_match_what_was_verified():
    """The subsumption above was verified against a specific declared set. If the brand
    adds a fourth blocked task status, the equivalence has to be re-checked rather than
    assumed — so this pins the input the claim was measured on.
    """
    import inspect

    from custom_components.eufy_vacuum.adapters.eufy import adapter as _eufy

    src = inspect.getsource(_eufy)
    assert '"blocked_task_status_states": ["Cleaning", "Returning", "Washing Mop"]' in src, (
        "the declared blocked_task_status_states changed; re-verify the coverage claim "
        "in adapters/config_schema.py and docs/dev/22-adapter-contract.md §5 against the "
        "new set before updating this test"
    )
