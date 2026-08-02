"""RP-032 (RF-28): services.yaml <-> hass.services.async_register parity gate.

The expansion-ready-seam pattern: instead of a hand-maintained checklist of
"every service has a schema, every service is documented, every documented
field is actually accepted", this DISCOVERS the registered-service surface by
walking the real registration code (AST) and cross-checks it against
services.yaml and each schema's own field set. A service or field added later
is caught automatically -- nobody has to remember to update a checklist.

Four assertions, each independent:
  1. every hass.services.async_register(...) call has a schema (not None).
  2. every registered service has a services.yaml entry OR is on the
     INTERNAL_SERVICES allowlist below (checked in, one comment per entry --
     Chris reviews this list; see the module docstring on INTERNAL_SERVICES).
  3. every services.yaml field exists in the schema with matching
     required-ness, in both directions (yaml has a field schema rejects;
     schema accepts a field yaml never mentions).
  4. no dead schemas: a module-level `vol.Schema(...)`/`vol.All(...)` constant
     defined but never referenced anywhere in its own file.

KNOWN GAP (transparent, not silent): field-parity (assertion 3) only covers
registrations whose `schema=` argument is a plain named reference (e.g.
`schema=_MY_SCHEMA`). Six registrations pass an INLINE `vol.Schema({...})`
literal directly in the call (five in services/adapter_config.py, one in
__init__.py's battery_rebaseline) -- these still count for assertions 1/2,
but are skipped for 3 since resolving an arbitrary inline AST expression to a
live object is out of scope for this gate. None of RP-032's known findings
touch those six.

EXPECTED_FAILURES is a seeded, dated escape hatch for violations found but
not yet fixed -- each entry names the specific (service, field) or (kind, id)
tuple and a one-line reason. A violation NOT on this list fails the test. The
list shrinks to empty as RP-032's content-fix commits land; it does not grow
after this packet closes without a fresh justification.

Run: docker pytest tests/unit/test_service_declaration_parity.py --no-cov
"""

from __future__ import annotations

import ast
import importlib
import re
from pathlib import Path

import pytest
import voluptuous as vol
import yaml

REPO_ROOT = Path(__file__).resolve().parents[2]
COMPONENT_ROOT = REPO_ROOT / "custom_components" / "eufy_vacuum"
SERVICES_YAML_PATH = COMPONENT_ROOT / "services.yaml"

# config_flow.py's vol.Schema is UI config/options-flow validation -- a
# different contract entirely, not part of the service call surface.
_EXCLUDE_FILES = {"config_flow.py"}

# ---------------------------------------------------------------------------
# INTERNAL_SERVICES -- services intentionally registered with NO services.yaml
# entry (not meant to be discovered through Developer Tools / the automation
# UI's service picker the normal way). THE ALLOWLIST NEEDS A HUMAN: Chris
# reviews this list at RP-032's review. Every entry needs a comment saying
# WHY it's here instead of in services.yaml. Do not add an entry to make the
# gate pass without that review -- a service missing a descriptor by omission
# belongs in services.yaml, not here.
# ---------------------------------------------------------------------------
INTERNAL_SERVICES: dict[str, str] = {}

# ---------------------------------------------------------------------------
# EXPECTED_FAILURES -- seeded 2026-08-02 (RP-032 commit a) with everything
# the gate found on its first real run against this codebase. Format:
# {(kind, key): "reason"}. kind is one of "no_schema", "no_yaml_entry",
# "field_mismatch", "dead_schema". Entries are removed (never added to,
# without a fresh justification) as RP-032's content-fix commits land --
# see the per-category TODO comments below for the intended fix.
# ---------------------------------------------------------------------------
EXPECTED_FAILURES: dict[tuple[str, str], str] = {
    # --- no_schema: WIRE-4, fix = add schema=vol.Schema({}) ----------------
    ("no_schema", "get_room_profiles"): "WIRE-4: the only registration (of 142) with no schema at all.",

    # --- no_yaml_entry: 26 candidates for INTERNAL_SERVICES vs a real ------
    # --- services.yaml descriptor. THE ALLOWLIST NEEDS A HUMAN -- these ----
    # --- are grouped by likely disposition but none are decided yet. -------
    ("no_yaml_entry", "save_adapter_config"): "adapter_config.py: likely internal/dev-tool -- pending Chris review.",
    ("no_yaml_entry", "delete_adapter_config"): "adapter_config.py: likely internal/dev-tool -- pending Chris review.",
    ("no_yaml_entry", "get_adapter_config"): "adapter_config.py: likely internal/dev-tool -- pending Chris review.",
    ("no_yaml_entry", "discover_adapter_entities"): "adapter_config.py: likely internal/dev-tool -- pending Chris review.",
    ("no_yaml_entry", "observe_entity_states"): "adapter_config.py: likely internal/dev-tool -- pending Chris review.",
    ("no_yaml_entry", "set_dock_event_count"): "dock.py: likely diagnostic/test-only -- pending Chris review.",
    ("no_yaml_entry", "setup_get_status"): "setup.py: panel-driven (const.py's own grouping comment) -- pending Chris review.",
    ("no_yaml_entry", "setup_add_vacuum"): "setup.py: panel-driven -- pending Chris review.",
    ("no_yaml_entry", "setup_import_active_map"): "setup.py: panel-driven -- pending Chris review.",
    ("no_yaml_entry", "setup_get_map_rooms"): "setup.py: panel-driven -- pending Chris review.",
    ("no_yaml_entry", "setup_save_rooms"): "setup.py: panel-driven -- pending Chris review.",
    ("no_yaml_entry", "setup_delete_map"): "setup.py: panel-driven -- pending Chris review.",
    ("no_yaml_entry", "setup_reject_rooms"): "setup.py: panel-driven -- pending Chris review.",
    ("no_yaml_entry", "setup_force_remove_room"): "setup.py: panel-driven -- pending Chris review.",
    ("no_yaml_entry", "setup_set_panel_title"): "setup.py: panel-driven -- pending Chris review.",
    ("no_yaml_entry", "setup_set_map_camera"): "setup.py: panel-driven -- pending Chris review.",
    ("no_yaml_entry", "upload_map_image"): "mapping_services.py: card-driven map upload flow -- pending Chris review.",
    ("no_yaml_entry", "delete_map_image"): "mapping_services.py: card-driven -- pending Chris review.",
    ("no_yaml_entry", "analyze_map_image"): "mapping_services.py: card-driven -- pending Chris review.",
    ("no_yaml_entry", "get_map_segments"): "mapping_services.py: card-driven -- pending Chris review.",
    ("no_yaml_entry", "adjust_map_segment"): "mapping_services.py: card-driven -- pending Chris review.",
    ("no_yaml_entry", "confirm_external_run"): "learning/services.py: card review-wizard flow -- pending Chris review.",
    ("no_yaml_entry", "get_external_pending_runs"): "learning/services.py: card review-wizard flow -- pending Chris review.",
    ("no_yaml_entry", "discard_external_run"): "learning/services.py: card review-wizard flow -- pending Chris review.",
    ("no_yaml_entry", "resegment_external_run"): "learning/services.py: card review-wizard flow -- pending Chris review.",
    ("no_yaml_entry", "get_trouble_rooms_log"): "learning/services.py: card diagnostics -- pending Chris review.",
    ("no_yaml_entry", "get_incomplete_run_log"): "learning/services.py: card diagnostics -- pending Chris review.",

    # --- field_mismatch: map_id required-vs-docs-optional (SVC-9 + the -----
    # --- mapping_services.py cohort RP-028's resolver adoption covers) -----
    # SVC-9's 4 (save_learning_snapshot, finalize_learning_job,
    # run_learning_estimate, get_room_learning_estimates) fixed: schemas now
    # vol.Optional("map_id"), handlers route through resolved_call_data.
    ("field_mismatch", "set_area_label_anchor.map_id:requiredness"): "RP-028-adjacent (mapping_services.py resolved_call_data adoption); RP-028 unlanded, fixing narrowly here instead.",
    ("field_mismatch", "set_companion_anchor.map_id:requiredness"): "RP-028-adjacent, same fix.",
    ("field_mismatch", "set_furnished_art_placement.map_id:requiredness"): "RP-028-adjacent, same fix.",
    ("field_mismatch", "set_furnished_render_mode.map_id:requiredness"): "RP-028-adjacent, same fix.",
    ("field_mismatch", "set_hidden_regions.map_id:requiredness"): "RP-028-adjacent, same fix.",
    ("field_mismatch", "set_live_map_rotation.map_id:requiredness"): "RP-028-adjacent, same fix.",
    ("field_mismatch", "set_room_viewport.map_id:requiredness"): "RP-028-adjacent, same fix.",
    ("field_mismatch", "set_segment_room_link.map_id:requiredness"): "RP-028-adjacent, same fix.",

    # --- field_mismatch: carpet/floor_type, verified against the manager ---
    # --- (core/manager.py, profiles/manager.py, rooms/room_crud.py) --------
    ("field_mismatch", "save_managed_rooms.floor_types:yaml_only"): "manager genuinely accepts floor_types (rooms/room_crud.py:save_managed_rooms) -- add to schema.",
    ("field_mismatch", "save_managed_rooms.carpet_types:yaml_only"): "manager has no carpet_types concept (floor_type is compound, e.g. carpet_low_pile) -- stale yaml, remove from services.yaml.",
    ("field_mismatch", "save_managed_rooms.enabled_room_ids:requiredness"): "RP-005 established omit-to-keep-selection contract -- yaml's required:true is what's wrong, fix the doc not the schema.",
    ("field_mismatch", "save_user_room_profile.carpet:yaml_only"): "profiles carry no floor/carpet data (ProfileManager.save_user_room_profile has no such param) -- stale yaml, remove.",
    ("field_mismatch", "overwrite_room_profile.carpet:yaml_only"): "same as save_user_room_profile -- stale yaml, remove.",

    # --- field_mismatch: schema accepts a field yaml never documents -------
    # --- (each needs its own check: real accepted field -> add to yaml) ----
    ("field_mismatch", "create_custom_layout.backdrop_source:schema_only"): "undocumented accepted field -- verify then add to services.yaml.",
    ("field_mismatch", "finalize_learning_job.forced_outcome_status:schema_only"): "undocumented accepted field -- verify then add to services.yaml.",
    ("field_mismatch", "import_theme.vacuum_entity_id:schema_only"): "undocumented accepted field -- verify then add to services.yaml.",
    ("field_mismatch", "reanchor_learning_timeline.charge_percent_per_minute:schema_only"): "undocumented accepted field -- verify then add to services.yaml.",
    ("field_mismatch", "reanchor_learning_timeline.reserve_battery_percent:schema_only"): "undocumented accepted field -- verify then add to services.yaml.",
    ("field_mismatch", "reconcile_room.force:schema_only"): "undocumented accepted field -- verify then add to services.yaml.",
    ("field_mismatch", "set_custom_segments.backdrop_height:schema_only"): "undocumented accepted field -- verify then add to services.yaml.",
    ("field_mismatch", "set_custom_segments.backdrop_width:schema_only"): "undocumented accepted field -- verify then add to services.yaml.",
    ("field_mismatch", "start_selected_rooms.pause_timeout_minutes_override:schema_only"): "undocumented accepted field -- verify then add to services.yaml.",
    ("field_mismatch", "update_room_fields.color:schema_only"): "undocumented accepted field -- verify then add to services.yaml.",
    ("field_mismatch", "update_room_fields.is_transition:schema_only"): "undocumented accepted field -- verify then add to services.yaml.",

    # --- dead_schema: SERVIC-7, 19 unreferenced constants in one file ------
    ("dead_schema", "custom_components/eufy_vacuum/mapping/mapping_services.py::SAVE_MAP_IMAGE_SCHEMA"): "SERVIC-7",
    ("dead_schema", "custom_components/eufy_vacuum/mapping/mapping_services.py::START_ROOM_BOUNDARY_TRACE_SCHEMA"): "SERVIC-7",
    ("dead_schema", "custom_components/eufy_vacuum/mapping/mapping_services.py::CLOSE_ROOM_BOUNDARY_SCHEMA"): "SERVIC-7",
    ("dead_schema", "custom_components/eufy_vacuum/mapping/mapping_services.py::CANCEL_ROOM_BOUNDARY_TRACE_SCHEMA"): "SERVIC-7",
    ("dead_schema", "custom_components/eufy_vacuum/mapping/mapping_services.py::GET_MAPPING_STATE_SCHEMA"): "SERVIC-7",
    ("dead_schema", "custom_components/eufy_vacuum/mapping/mapping_services.py::CLEAR_ROOM_BOUNDS_SCHEMA"): "SERVIC-7",
    ("dead_schema", "custom_components/eufy_vacuum/mapping/mapping_services.py::EXCLUDE_ROOM_JOB_BOUNDS_SCHEMA"): "SERVIC-7",
    ("dead_schema", "custom_components/eufy_vacuum/mapping/mapping_services.py::RESTORE_ROOM_JOB_BOUNDS_SCHEMA"): "SERVIC-7",
    ("dead_schema", "custom_components/eufy_vacuum/mapping/mapping_services.py::REBUILD_ROOM_BOUNDS_SCHEMA"): "SERVIC-7",
    ("dead_schema", "custom_components/eufy_vacuum/mapping/mapping_services.py::SAVE_MAPPING_PACKAGE_SCHEMA"): "SERVIC-7",
    ("dead_schema", "custom_components/eufy_vacuum/mapping/mapping_services.py::APPEND_MAPPING_TRACE_EVIDENCE_SCHEMA"): "SERVIC-7",
    ("dead_schema", "custom_components/eufy_vacuum/mapping/mapping_services.py::GET_IMAGE_SEGMENT_SUGGESTIONS_SCHEMA"): "SERVIC-7",
    ("dead_schema", "custom_components/eufy_vacuum/mapping/mapping_services.py::TRANSLATE_IMAGE_SEGMENT_SCHEMA"): "SERVIC-7",
    ("dead_schema", "custom_components/eufy_vacuum/mapping/mapping_services.py::SET_DOCK_ANCHOR_SCHEMA"): "SERVIC-7",
    ("dead_schema", "custom_components/eufy_vacuum/mapping/mapping_services.py::SET_DOCK_ROOM_SCHEMA"): "SERVIC-7",
    ("dead_schema", "custom_components/eufy_vacuum/mapping/mapping_services.py::START_TRACE_CAPTURE_SCHEMA"): "SERVIC-7",
    ("dead_schema", "custom_components/eufy_vacuum/mapping/mapping_services.py::STOP_TRACE_CAPTURE_SCHEMA"): "SERVIC-7",
    ("dead_schema", "custom_components/eufy_vacuum/mapping/mapping_services.py::CANCEL_TRACE_CAPTURE_SCHEMA"): "SERVIC-7",
    ("dead_schema", "custom_components/eufy_vacuum/mapping/mapping_services.py::REVIEW_TRACE_RUN_SCHEMA"): "SERVIC-7",
}


# ---------------------------------------------------------------------------
# services.yaml
# ---------------------------------------------------------------------------

def _load_services_yaml() -> dict:
    return yaml.safe_load(SERVICES_YAML_PATH.read_text(encoding="utf-8"))


# ---------------------------------------------------------------------------
# AST discovery of every hass.services.async_register(...) call
# ---------------------------------------------------------------------------

def _iter_py_files():
    for path in sorted(COMPONENT_ROOT.rglob("*.py")):
        if path.name in _EXCLUDE_FILES:
            continue
        yield path


def _module_name_for(path: Path) -> str:
    rel = path.relative_to(REPO_ROOT).with_suffix("")
    return ".".join(rel.parts)


def _resolve_str(node: ast.expr | None, module_values: dict[str, object]) -> str | None:
    """Resolve a service-name AST node to its string value: a literal, or an
    identifier bound in the REGISTERING MODULE's own namespace -- which
    covers both `from ..const import SERVICE_X` (the import binds SERVICE_X
    into this module too) and a module-local constant (learning/services.py
    and debug_capture.py each define their own, not in const.py)."""
    if node is None:
        return None
    if isinstance(node, ast.Constant) and isinstance(node.value, str):
        return node.value
    ident = None
    if isinstance(node, ast.Name):
        ident = node.id
    elif isinstance(node, ast.Attribute):
        ident = node.attr
    if ident is None:
        return None
    value = module_values.get(ident)
    return value if isinstance(value, str) else None


def _is_async_register_call(node: ast.AST) -> bool:
    if not isinstance(node, ast.Call):
        return False
    func = node.func
    if not (isinstance(func, ast.Attribute) and func.attr == "async_register"):
        return False
    value = func.value
    return isinstance(value, ast.Attribute) and value.attr == "services"


class Registration:
    __slots__ = ("file", "lineno", "service_name", "has_schema", "schema_node", "module_name")

    def __init__(self, file, lineno, service_name, has_schema, schema_node, module_name):
        self.file = file
        self.lineno = lineno
        self.service_name = service_name
        self.has_schema = has_schema
        self.schema_node = schema_node
        self.module_name = module_name

    @property
    def label(self) -> str:
        return f"{self.service_name or '<unresolved>'} ({self.file}:{self.lineno})"


def _find_registrations() -> list[Registration]:
    registrations: list[Registration] = []
    for path in _iter_py_files():
        source = path.read_text(encoding="utf-8")
        try:
            tree = ast.parse(source, filename=str(path))
        except SyntaxError:  # pragma: no cover - defensive
            continue
        rel = path.relative_to(REPO_ROOT).as_posix()
        module_name = _module_name_for(path)
        calls = [node for node in ast.walk(tree) if _is_async_register_call(node)]
        if not calls:
            continue
        module = importlib.import_module(module_name)
        module_values = vars(module)
        for node in calls:
            args = node.args
            kwargs = {kw.arg: kw.value for kw in node.keywords if kw.arg}
            # signature: async_register(domain, service, service_func, schema=None, supports_response=...)
            service_node = args[1] if len(args) > 1 else kwargs.get("service")
            service_name = _resolve_str(service_node, module_values)
            schema_node = kwargs.get("schema")
            if schema_node is None and len(args) > 3:
                schema_node = args[3]
            has_schema = not (
                schema_node is None
                or (isinstance(schema_node, ast.Constant) and schema_node.value is None)
            )
            registrations.append(
                Registration(rel, node.lineno, service_name, has_schema, schema_node, module_name)
            )
    return registrations


# ---------------------------------------------------------------------------
# Resolving a NAMED schema reference to the real voluptuous object
# ---------------------------------------------------------------------------

def _resolve_schema_object(reg: Registration):
    """Return the live vol.Schema object for a registration's schema= arg, or
    None if it's not a simple module-level name reference (inline literal)."""
    if not isinstance(reg.schema_node, ast.Name):
        return None
    module = importlib.import_module(reg.module_name)
    return getattr(module, reg.schema_node.id, None)


def _schema_field_requiredness(schema_obj) -> dict[str, bool] | None:
    """{field_name: is_required} for a vol.Schema wrapping a dict, else None
    (the schema isn't a plain dict-shaped vol.Schema this gate can introspect,
    e.g. wraps a list or another combinator)."""
    if not isinstance(schema_obj, vol.Schema):
        return None
    inner = schema_obj.schema
    if not isinstance(inner, dict):
        return None
    out: dict[str, bool] = {}
    for marker in inner:
        key = str(marker)
        if isinstance(marker, vol.Required):
            out[key] = True
        elif isinstance(marker, vol.Optional):
            out[key] = False
        else:  # pragma: no cover - defensive, no bare-str keys used in this codebase
            out[key] = True
    return out


# ---------------------------------------------------------------------------
# Dead-schema scan: module-level `NAME = vol.Schema(...)` / `vol.All(...)`
# never referenced anywhere else in its own file's source.
# ---------------------------------------------------------------------------

def _is_schema_call(node: ast.expr) -> bool:
    if not isinstance(node, ast.Call):
        return False
    func = node.func
    if isinstance(func, ast.Attribute) and isinstance(func.value, ast.Name) and func.value.id == "vol":
        return func.attr in {"Schema", "All"}
    return False


def _find_dead_schemas() -> list[tuple[str, str]]:
    """[(file, schema_name), ...] for every module-level vol.Schema/vol.All
    constant whose name appears nowhere else in the COMPONENT (its own file
    minus the definition line, plus every other file -- a schema meant to be
    shared, like services/_common.py's VACUUM_ONLY_SCHEMA, is imported and
    referenced from a different file than the one that defines it)."""
    candidates: list[tuple[str, str, str]] = []  # (file, name, def_line_text)
    file_sources: dict[str, str] = {}
    for path in _iter_py_files():
        source = path.read_text(encoding="utf-8")
        rel = path.relative_to(REPO_ROOT).as_posix()
        file_sources[rel] = source
        try:
            tree = ast.parse(source, filename=str(path))
        except SyntaxError:  # pragma: no cover - defensive
            continue
        for node in tree.body:
            if not isinstance(node, ast.Assign) or len(node.targets) != 1:
                continue
            target = node.targets[0]
            if not isinstance(target, ast.Name):
                continue
            if not _is_schema_call(node.value):
                continue
            candidates.append((rel, target.id, node.lineno))

    dead: list[tuple[str, str]] = []
    for rel, name, def_lineno in candidates:
        pattern = re.compile(rf"\b{re.escape(name)}\b")
        referenced = False
        for other_rel, source in file_sources.items():
            lines = source.splitlines()
            def_line_idx = def_lineno - 1 if other_rel == rel else -1
            if any(
                pattern.search(line) for i, line in enumerate(lines) if i != def_line_idx
            ):
                referenced = True
                break
        if not referenced:
            dead.append((rel, name))
    return dead


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------

def _expected(kind: str, key: str) -> str | None:
    return EXPECTED_FAILURES.get((kind, key))


def test_every_registered_service_has_a_schema():
    registrations = _find_registrations()
    assert registrations, "AST walk found zero hass.services.async_register(...) calls -- gate is broken"
    unexpected = []
    for reg in registrations:
        if reg.has_schema:
            continue
        reason = _expected("no_schema", reg.service_name or reg.label)
        if reason is None:
            unexpected.append(reg.label)
    assert not unexpected, (
        "registered with no schema (add schema=vol.Schema({}) at minimum), "
        f"not on EXPECTED_FAILURES: {unexpected}"
    )


def test_every_service_documented_or_internal():
    registrations = _find_registrations()
    yaml_services = set(_load_services_yaml().keys())
    unexpected = []
    for reg in registrations:
        name = reg.service_name
        if name is None:
            continue  # unresolvable service name is a distinct problem the AST-shape assertion below covers
        if name in yaml_services or name in INTERNAL_SERVICES:
            continue
        reason = _expected("no_yaml_entry", name)
        if reason is None:
            unexpected.append(f"{name} ({reg.file}:{reg.lineno})")
    assert not unexpected, (
        "registered service has no services.yaml entry and is not on "
        f"INTERNAL_SERVICES, not on EXPECTED_FAILURES: {unexpected}"
    )


def test_every_registration_has_a_resolvable_service_name():
    """A registration whose service-name argument this gate can't resolve to
    a string (neither a literal nor a SERVICE_* const) is invisible to the
    other three assertions -- that's a gap in the gate itself, not something
    EXPECTED_FAILURES should paper over."""
    registrations = _find_registrations()
    unresolved = [f"{reg.file}:{reg.lineno}" for reg in registrations if reg.service_name is None]
    assert not unresolved, f"could not resolve the service name for: {unresolved}"


def test_services_yaml_field_parity():
    registrations = _find_registrations()
    yaml_data = _load_services_yaml()
    unexpected = []

    for reg in registrations:
        name = reg.service_name
        if name is None or name not in yaml_data:
            continue
        schema_obj = _resolve_schema_object(reg)
        if schema_obj is None:
            continue  # inline schema literal -- documented gate scope limit, see module docstring
        schema_fields = _schema_field_requiredness(schema_obj)
        if schema_fields is None:
            continue  # not a plain dict-shaped schema this gate introspects

        yaml_fields = (yaml_data[name] or {}).get("fields") or {}
        yaml_required = {
            field: bool(spec.get("required", False)) for field, spec in yaml_fields.items()
        }

        for field, required in yaml_required.items():
            key = f"{name}.{field}"
            if field not in schema_fields:
                reason = _expected("field_mismatch", f"{key}:yaml_only")
                if reason is None:
                    unexpected.append(f"{key}: services.yaml declares it, schema rejects it (extra key)")
                continue
            if schema_fields[field] != required:
                reason = _expected("field_mismatch", f"{key}:requiredness")
                if reason is None:
                    unexpected.append(
                        f"{key}: services.yaml required={required}, "
                        f"schema required={schema_fields[field]}"
                    )

        for field in schema_fields:
            if field in yaml_required:
                continue
            key = f"{name}.{field}"
            reason = _expected("field_mismatch", f"{key}:schema_only")
            if reason is None:
                unexpected.append(f"{key}: schema accepts it, services.yaml never documents it")

    assert not unexpected, "services.yaml <-> schema field parity violations:\n" + "\n".join(
        sorted(unexpected)
    )


def test_no_dead_schemas():
    dead = _find_dead_schemas()
    unexpected = []
    for file, name in dead:
        reason = _expected("dead_schema", f"{file}::{name}")
        if reason is None:
            unexpected.append(f"{file}::{name}")
    assert not unexpected, f"defined-but-unreferenced schema constants: {sorted(unexpected)}"


def test_expected_failures_do_not_rot():
    """Every EXPECTED_FAILURES entry must still reproduce -- an emptied
    violation left behind here would silently mask a regression the day
    someone re-breaks it, since the (now-passing) case would just look like
    an allowlisted failure forever. This test is the reverse of the other
    four: it fails if an expected failure has quietly started passing."""
    if not EXPECTED_FAILURES:
        pytest.skip("no expected failures to check")
    still_failing = _collect_all_failure_keys()
    stale = [key for key in EXPECTED_FAILURES if key not in still_failing]
    assert not stale, (
        f"EXPECTED_FAILURES entries that no longer reproduce -- remove them: {stale}"
    )


def _collect_all_failure_keys() -> set[tuple[str, str]]:
    """Re-run all four checks WITHOUT the allowlist filter, returning every
    (kind, key) that currently violates -- used only to detect stale
    EXPECTED_FAILURES entries above."""
    keys: set[tuple[str, str]] = set()
    registrations = _find_registrations()
    yaml_data = _load_services_yaml()
    yaml_services = set(yaml_data.keys())

    for reg in registrations:
        if not reg.has_schema:
            keys.add(("no_schema", reg.service_name or reg.label))
        name = reg.service_name
        if name and name not in yaml_services and name not in INTERNAL_SERVICES:
            keys.add(("no_yaml_entry", name))
        if name and name in yaml_data:
            schema_obj = _resolve_schema_object(reg)
            if schema_obj is not None:
                schema_fields = _schema_field_requiredness(schema_obj)
                if schema_fields is not None:
                    yaml_fields = (yaml_data[name] or {}).get("fields") or {}
                    yaml_required = {
                        f: bool(s.get("required", False)) for f, s in yaml_fields.items()
                    }
                    for field, required in yaml_required.items():
                        k = f"{name}.{field}"
                        if field not in schema_fields:
                            keys.add(("field_mismatch", f"{k}:yaml_only"))
                        elif schema_fields[field] != required:
                            keys.add(("field_mismatch", f"{k}:requiredness"))
                    for field in schema_fields:
                        if field not in yaml_required:
                            keys.add(("field_mismatch", f"{name}.{field}:schema_only"))

    for file, name in _find_dead_schemas():
        keys.add(("dead_schema", f"{file}::{name}"))

    return keys
