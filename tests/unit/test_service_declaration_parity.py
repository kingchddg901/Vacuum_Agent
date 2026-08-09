"""RP-032 (RF-28): services.yaml <-> hass.services.async_register parity gate.

The expansion-ready-seam pattern: instead of a hand-maintained checklist of
"every service has a schema, every service is documented, every documented
field is actually accepted", this DISCOVERS the registered-service surface by
walking the real registration code (AST) and cross-checks it against
services.yaml and each schema's own field set. A service or field added later
is caught automatically -- nobody has to remember to update a checklist.

Five assertions, each independent:
  1. every hass.services.async_register(...) call has a schema (not None).
  2. every registered service has a services.yaml entry OR is on the
     INTERNAL_SERVICES allowlist below (checked in, one comment per entry --
     Chris reviews this list; see the module docstring on INTERNAL_SERVICES).
  3. every services.yaml field exists in the schema with matching
     required-ness, in both directions (yaml has a field schema rejects;
     schema accepts a field yaml never mentions).
  4. no dead schemas: a module-level `vol.Schema(...)`/`vol.All(...)` constant
     defined but never referenced anywhere in its own file.
  5. the debug-capture `areas` selector in services.yaml matches EUFY_AREAS —
     the same list written twice, where drift silently makes an area either
     unselectable or rejected on use.

THE INTERNAL_SERVICES RULE (Chris, 2026-08-02 -- the no_yaml_entry ruling in
.claude/notes/synthesis/SYNTH-10-packets-wave6.md; centralizing the QUESTION,
not a vocabulary list, is the point -- a new service earns its classification
by answering this, not by pattern-matching an existing entry):

  A service earns a services.yaml entry if a human calling it BY HAND is
  COHERENT -- it takes arguments a person can type and does something a
  person would want. It stays on INTERNAL_SERVICES if it is a HANDSHAKE: an
  opaque payload the panel/card constructs, or a response only the card
  consumes.

  OVERRIDE: anything DESTRUCTIVE gets an entry regardless of the above. The
  yaml entry IS the documentation and the Developer Tools field editor; a
  service that deletes must never be the least-documented thing in the tree.

  This is a judgment call, not something this gate can check mechanically --
  a new no_yaml_entry violation still needs a human to apply the rule above
  and either add a services.yaml entry or a commented INTERNAL_SERVICES
  entry. The gate only guarantees the question gets asked (nothing lands
  silently undocumented); it cannot answer the question itself.

KNOWN GAP (transparent, not silent): field-parity (assertion 3) only covers
registrations whose `schema=` argument is a plain named reference (e.g.
`schema=_MY_SCHEMA`). Six registrations pass an INLINE `vol.Schema({...})`
literal directly in the call (five in services/adapter_config.py, one in
__init__.py's battery_rebaseline) -- these still count for assertions 1/2,
but are skipped for 3 since resolving an arbitrary inline AST expression to a
live object is out of scope for this gate. None of RP-032's known findings
touch those six. (The five in adapter_config.py are INTERNAL_SERVICES, so
they never reach the schema step at all; battery_rebaseline is the only
DOCUMENTED service the schema step itself has to skip.)

THE GAP IS PINNED, NOT TOLERATED (2026-08-07): assertion 3 used to `continue`
past every skip silently and assert only on the violations it found, so a
tree where NOTHING resolved -- every named schema converted to an inline
literal, or one constant renamed out from under `getattr` -- compared zero
services against services.yaml and still passed green. FIELD_PARITY_UNRESOLVED
below names the exact skips that are allowed; anything else leaving the
checked set now fails, and so does an entry here that starts resolving again.

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
# entry. See THE INTERNAL_SERVICES RULE in the module docstring above for the
# actual test to apply -- every entry needs a comment saying WHY it passes
# that test, not just "pending review". Do not add an entry to make the gate
# pass without applying the rule -- a service missing a descriptor by
# omission belongs in services.yaml, not here.
# ---------------------------------------------------------------------------
INTERNAL_SERVICES: dict[str, str] = {
    # setup.py x10 -- wizard step sequence; each step is meaningless called
    # out of order. Chris's ruling places setup_delete_map here despite it
    # being destructive (deletes a map, gated by its own confirmation_token
    # step for elevated/high-risk cases) -- an explicit call, not an
    # oversight, so it is NOT re-litigated against the destructive-override
    # line in the rule above.
    "setup_get_status": "setup.py: wizard step, panel-driven -- handshake.",
    "setup_add_vacuum": "setup.py: wizard step, panel-driven -- handshake.",
    "setup_import_active_map": "setup.py: wizard step, panel-driven -- handshake.",
    "setup_get_map_rooms": "setup.py: wizard step, panel-driven -- handshake.",
    "setup_save_rooms": "setup.py: wizard step, panel-driven -- handshake.",
    "setup_delete_map": "setup.py: wizard step, panel-driven -- handshake. Destructive but explicitly ruled internal by Chris (2026-08-02), not an oversight -- gated by its own confirmation_token step.",
    "setup_reject_rooms": "setup.py: wizard step, panel-driven -- handshake.",
    "setup_force_remove_room": "setup.py: wizard step, panel-driven -- handshake.",
    "setup_set_panel_title": "setup.py: wizard step, panel-driven -- handshake.",
    "setup_set_map_camera": "setup.py: wizard step, panel-driven -- handshake.",
    # adapter_config.py x5 -- panel discovery/observe handshakes; opaque
    # payloads the adapter-config panel constructs, not human-typeable.
    "save_adapter_config": "adapter_config.py: panel-constructed config payload -- handshake.",
    "delete_adapter_config": "adapter_config.py: panel discovery handshake.",
    "get_adapter_config": "adapter_config.py: panel discovery handshake.",
    "discover_adapter_entities": "adapter_config.py: panel discovery handshake.",
    "observe_entity_states": "adapter_config.py: panel observe handshake.",
    # mapping_services.py x4 -- base64 image blobs and geometry payloads the
    # card constructs; hand-calling is incoherent. delete_map_image, the
    # fifth service in this same registration block, crossed the line on
    # the destructive override instead -- see services.yaml.
    "upload_map_image": "mapping_services.py: base64 image payload -- handshake.",
    "analyze_map_image": "mapping_services.py: geometry/segment payload -- handshake.",
    "get_map_segments": "mapping_services.py: card-consumed response only -- handshake.",
    "adjust_map_segment": "mapping_services.py: geometry payload -- handshake.",
}

# ---------------------------------------------------------------------------
# FIELD_PARITY_UNRESOLVED -- the DOCUMENTED services (they have a
# services.yaml entry) that assertion 3 cannot field-check, because their
# `schema=` argument is not a plain module-level name this gate can resolve to
# a live voluptuous object, or resolves to something that is not a
# dict-shaped vol.Schema. See "THE GAP IS PINNED" in the module docstring:
# this list is the gate's own coverage measurement, not an excuse list. Adding
# an entry means the (service, field) pairs behind it are UNCHECKED by every
# assertion in this file -- prefer hoisting the schema to a module-level
# constant, which makes it checkable, over adding a line here.
# ---------------------------------------------------------------------------
FIELD_PARITY_UNRESOLVED: dict[str, str] = {
    "battery_rebaseline": (
        "__init__.py: schema= is an inline vol.Schema({...}) literal in the "
        "register call, so there is no named constant to resolve."
    ),
}

# ---------------------------------------------------------------------------
# EXPECTED_FAILURES -- seeded 2026-08-02 (RP-032 commit a) with everything
# the gate found on its first real run against this codebase. Format:
# {(kind, key): "reason"}. kind is one of "no_schema", "no_yaml_entry",
# "field_mismatch", "dead_schema". Entries are removed (never added to,
# without a fresh justification) as RP-032's content-fix commits land --
# see the per-category TODO comments below for the intended fix.
# ---------------------------------------------------------------------------
EXPECTED_FAILURES: dict[tuple[str, str], str] = {
    # WIRE-4 fixed: get_room_profiles now registers with schema=vol.Schema({}).

    # no_yaml_entry: FULLY RESOLVED, all 27 -- see Chris's no_yaml_entry
    # ruling (.claude/notes/synthesis/SYNTH-10-packets-wave6.md, "RP-032 --
    # no_yaml_entry ruling"), applying THE INTERNAL_SERVICES RULE in this
    # module's docstring. 8 got real services.yaml entries (delete_map_image,
    # set_dock_event_count, resegment_external_run, get_incomplete_run_log,
    # get_trouble_rooms_log, confirm_external_run, get_external_pending_runs,
    # discard_external_run); 19 moved to INTERNAL_SERVICES above with their
    # own per-entry comments.
    #
    # The last 3 (all learning/services.py) needed a second round: they
    # weren't in the ruling's first-pass tables at all -- not because they're
    # unclassifiable, but because the main agent's classification pass was
    # seeded from const.py and these three are declared INLINE beside their
    # own schemas (e.g. SERVICE_CONFIRM_EXTERNAL_RUN at services.py:213), so
    # a const.py-only grep never saw them. Escalating instead of guessing
    # (per the ruling's own "stop and escalate" instruction) is what
    # surfaced the gap and got them ruled on explicitly: confirm_external_run
    # mutates learning permanently (structured-but-typeable payload, not an
    # opaque blob); get_external_pending_runs is the ONLY way to obtain the
    # pending_job_id the other two require, so leaving it internal would
    # strand them; discard_external_run is destructive (deletes a captured
    # run). Documenting only part of a flow was itself flagged as the defect
    # class this campaign keeps finding.

    # field_mismatch: map_id required-vs-docs-optional, mapping_services.py cohort --
    # FIXED (RP-032): all 8 schemas switched vol.Required(map_id) -> vol.Optional,
    # with a shared _resolve_write_map_bucket() resolver (active map, then the first
    # stored map, else refuse) + require_map_bucket (never a phantom bucket for an
    # unknown map_id) landed alongside, matching the already-shipped
    # _handle_set_map_overlay_visibility / _handle_create_saved_zone precedent this
    # allowlist used to say was still pending.

    # carpet/floor_type group fixed: floor_types added to
    # _SAVE_MANAGED_ROOMS_SCHEMA (manager genuinely accepts it);
    # carpet_types removed from services.yaml (no manager equivalent --
    # floor_type is a compound value, e.g. carpet_low_pile); carpet removed
    # from save_user_room_profile/overwrite_room_profile's services.yaml
    # entries (profiles carry no floor/carpet data); enabled_room_ids's
    # services.yaml required:true corrected to false (RP-005's established
    # omit-to-keep-selection contract).

    # schema_only group fixed: all 11 fields were genuinely accepted by their
    # schema and reachable from the handler to a real manager/estimator
    # kwarg -- each got a services.yaml field doc (create_custom_layout
    # backdrop_source; set_custom_segments backdrop_width/backdrop_height,
    # plus its description rewritten -- CUSTOM-7; finalize_learning_job
    # forced_outcome_status; import_theme vacuum_entity_id -- scoped-import
    # target; reanchor_learning_timeline charge_percent_per_minute/
    # reserve_battery_percent; reconcile_room force; update_room_fields
    # color/is_transition). start_selected_rooms.pause_timeout_minutes_override
    # was a services.yaml copy-paste bug, not a missing doc: the field block
    # was attached to battery_rebaseline (whose real inline schema is
    # vacuum_entity_id only -- documenting a field it doesn't accept) instead
    # of start_selected_rooms (whose schema does have it); moved, not added.

    # SERVIC-7 fixed: all 19 unreferenced schema constants deleted from
    # mapping_services.py (they were never used by any registration call).
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
    e.g. wraps a list or another combinator).

    A registration's schema= may be `vol.All(..., vol.Schema({...}), ...)`
    (a cross-field check layered on a per-key schema, e.g. queue.py's break
    schemas -- RP-032/A2-JOB-5/6): unwrap to the first vol.Schema among
    vol.All's sub-validators rather than losing field-parity coverage for it.
    """
    if isinstance(schema_obj, vol.All):
        for validator in schema_obj.validators:
            if isinstance(validator, vol.Schema):
                schema_obj = validator
                break
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


def test_every_services_yaml_entry_is_actually_registered():
    """The OTHER direction. A services.yaml entry with no handler is a service
    Home Assistant offers in Developer Tools -> Actions and that fails when called.

    Found live: `debug_log_live_room` survived in services.yaml for a month after
    its handler was deleted (cb68ece, the mapping split), because every assertion
    in this file walked registrations -> yaml and none walked yaml -> registrations.
    A gate whose window closes just short of a failure reads exactly like a gate
    that passed, and this file's own name promises parity, which is why nobody
    looked. Deleting a handler is the normal way this arises; the yaml entry is
    the easiest half to forget.
    """
    registered = {
        reg.service_name for reg in _find_registrations() if reg.service_name is not None
    }
    orphaned = sorted(set(_load_services_yaml().keys()) - registered)
    assert not orphaned, (
        "services.yaml declares services that nothing registers, so Home Assistant "
        f"will offer them and they will fail when called: {orphaned}"
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
    # WHAT THIS GATE ACTUALLY LOOKED AT. Every `continue` below is a service
    # whose fields nothing in this file compares against services.yaml, and a
    # gate that skips everything reports the same clean result as a gate that
    # finds nothing wrong. Both sets are asserted on at the bottom.
    checked: set[str] = set()
    unresolved: dict[str, str] = {}

    for reg in registrations:
        name = reg.service_name
        if name is None or name not in yaml_data:
            continue  # undocumented/internal -- assertions 2 and 3b own that gate
        schema_obj = _resolve_schema_object(reg)
        if schema_obj is None:
            # inline schema literal / getattr miss -- documented gate scope limit
            unresolved[name] = (
                f"schema= is not a resolvable module-level name ({reg.file}:{reg.lineno})"
            )
            continue
        schema_fields = _schema_field_requiredness(schema_obj)
        if schema_fields is None:
            unresolved[name] = (
                f"schema is not a plain dict-shaped vol.Schema ({reg.file}:{reg.lineno})"
            )
            continue
        checked.add(name)

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

    # --- the gate measured SOMETHING (mirrors assertion 1's `assert registrations`) ---
    assert checked, (
        "field parity compared ZERO services against services.yaml -- every "
        "registration was skipped, so this assertion proves nothing. Skips: "
        f"{sorted(unresolved)}"
    )
    # --- and it measured everything it is supposed to ---
    newly_unresolved = sorted(set(unresolved) - set(FIELD_PARITY_UNRESOLVED))
    assert not newly_unresolved, (
        "these DOCUMENTED services dropped out of field parity and are now "
        "unchecked in both directions -- hoist the schema to a module-level "
        "constant, or add it to FIELD_PARITY_UNRESOLVED with a reason:\n"
        + "\n".join(f"  {n}: {unresolved[n]}" for n in newly_unresolved)
    )
    rotted = sorted(set(FIELD_PARITY_UNRESOLVED) - set(unresolved))
    assert not rotted, (
        "FIELD_PARITY_UNRESOLVED entries that now resolve fine -- remove them, "
        f"otherwise they mask the day the schema goes un-introspectable again: {rotted}"
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


def test_debug_capture_area_options_match_configured_areas():
    """5. the areas SELECTOR in services.yaml lists exactly the areas the
    recorder actually knows about.

    The same list is written twice — once as EUFY_AREAS (which _resolve_areas
    validates against, raising on an unknown name) and once as the services.yaml
    select options (which is all the UI ever offers). Drift is silent in both
    directions and each direction is its own failure:

      yaml-only  -> the UI offers an area that _resolve_areas REJECTS, so
                    starting a capture fails with a validation error.
      code-only  -> an area exists but nothing can select it, so the loggers it
                    scopes are reachable ONLY by selecting no area at all and
                    taking the whole tree. That is exactly how `decisions`
                    (the decision_log scope, where the issue #46 observation
                    trace lands) was unreachable from the UI.

    Not a checklist: it derives both sides and diffs them, so a future area is
    covered without anyone remembering this test exists.
    """
    from custom_components.eufy_vacuum.services.debug import EUFY_AREAS

    options = (
        _load_services_yaml()["debug_capture_start"]["fields"]["areas"]
        ["selector"]["select"]["options"]
    )
    yaml_only = sorted(set(options) - set(EUFY_AREAS))
    code_only = sorted(set(EUFY_AREAS) - set(options))
    assert not yaml_only and not code_only, (
        "services.yaml areas selector has drifted from EUFY_AREAS — "
        f"offered but unknown to the recorder: {yaml_only or 'none'}; "
        f"known but not offered: {code_only or 'none'}"
    )


# ---------------------------------------------------------------------------
# 6. no duplicate sibling keys in services.yaml
#
# yaml.safe_load takes the LAST of a duplicated key and says nothing, so a
# copy-paste that leaves two `selector:` blocks under one field parses cleanly
# and ships. Found live on 2026-08-05: reconcile_room's `plan_token` carried
# `selector: text` followed by `selector: boolean`, so a field the schema
# declares `cv.string` and that is REQUIRED for action=migrate rendered as a
# toggle -- the migrate path was uncallable from the UI. Present since
# 0e0369f (2026-08-02).
#
# Home Assistant's own loader DOES warn ("contains duplicate key"), which is how
# it surfaced -- but only in the core log, at startup, on a running instance.
# Every gate in this file ran green over it for three days. A warning nobody
# reads is not a gate.
# ---------------------------------------------------------------------------

class _DuplicateKeyLoader(yaml.SafeLoader):
    """SafeLoader that records duplicate mapping keys instead of silently merging."""

    duplicates: list[tuple[str, int, int]] = []

    def construct_mapping(self, node, deep=False):  # noqa: D102
        seen: dict = {}
        for key_node, _value_node in node.value:
            key = self.construct_object(key_node, deep=deep)
            if key in seen:
                _DuplicateKeyLoader.duplicates.append(
                    (str(key), seen[key], key_node.start_mark.line + 1)
                )
            seen[key] = key_node.start_mark.line + 1
        return super().construct_mapping(node, deep=deep)


def test_services_yaml_has_no_duplicate_keys():
    """A duplicated key parses fine and silently discards one of the two values."""
    _DuplicateKeyLoader.duplicates = []
    yaml.load(SERVICES_YAML_PATH.read_text(encoding="utf-8"), Loader=_DuplicateKeyLoader)
    dupes = _DuplicateKeyLoader.duplicates
    assert not dupes, (
        "duplicate keys in services.yaml -- the later value silently wins:\n"
        + "\n".join(f"  '{k}' at lines {a} and {b}" for k, a, b in dupes)
    )
