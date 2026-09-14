#!/usr/bin/env python3
"""
Generated adapter-config reference + capability-flag reference.

Candidate replacements for `docs/dev/22-adapter-config-reference.md` and the
capability sections of `docs/dev/21-adapter-system.md`. NOTHING HERE IS
COMMITTED and no tracked file is touched: script and output both live under
`.claude/`, which .gitignore excludes wholesale.

Follows the shape of `.claude/generated-docs/gen_service_docs.py`:
sources -> resolved model -> candidate doc + drift report + blind-spot ledger.

SOURCES (five, not one -- this is the finding that shaped the script):

  1. adapters/config_schema.py  ADAPTER_CONFIG_SCHEMA -- the declared contract.
     NOTE it is `ADAPTER_CONFIG_SCHEMA: dict[str, dict] = {...}`, an ast.AnnAssign.
     A walk matching only ast.Assign finds ZERO keys and reports a confident
     empty answer.
  2. adapters/config_schema.py  validate_against_schema() -- which spec keys the
     walker actually ENFORCES. A spec key the schema uses but the walker never
     reads is decoration, not contract.
  3. core/capabilities.py       KNOWN_CAPABILITY_HINTS + detect_capabilities().
     THREE capability namespaces exist and share key names:
       - the `capabilities` config block   (adapter-literal, read by dispatch/card)
       - the `capability_hints` config block (fed INTO detection; the ONLY set
         validated at registration, against KNOWN_CAPABILITY_HINTS)
       - detect_capabilities()'s RETURN     (the runtime payload)
     Conflating them is what produces three different "flag counts" for one set.
  4. adapters/registry.py       _validate_adapter() -- registration-time checks
     that exist for some blocks and not others. Not visible from the schema.
  5. the two shipped adapters   eufy/adapter.py, roborock/adapter.py -- which
     declared keys anything actually ships. A key nobody declares is a contract
     with no witness.

THE GENERATOR DECLARES ITS BLIND SPOTS (design note 4.2). Everything that could
not be resolved statically is counted and listed. Silence is the failure mode.

    python scripts/gen_adapter_config_docs.py
"""
from __future__ import annotations

import ast
import json
import os
import re
from collections import defaultdict
from dataclasses import dataclass, field
from pathlib import Path

HERE = Path(__file__).resolve().parent          # <repo>/scripts
ROOT = Path(os.environ.get("EVCC_ADAPTER_DOC_ROOT") or HERE.parent)
# `EVCC_GENDOC_OUT` is the variable scripts/check_generated_docs.py sets when it
# regenerates into a scratch dir to diff against the committed copy — the same
# contract the theme-token and events generators honour. `EVCC_ADAPTER_DOC_OUT`
# stays as an alias because it predates the move and is in muscle memory.
OUT = Path(
    os.environ.get("EVCC_GENDOC_OUT")
    or os.environ.get("EVCC_ADAPTER_DOC_OUT")
    or (ROOT / "docs" / "dev" / "reference")
)
OUT.mkdir(parents=True, exist_ok=True)

# THE TWO PUBLISHED FILES GO TO `OUT`; THE WORKING ARTIFACTS DO NOT. The drift report and
# the index JSON are inputs to a person auditing this generator, not documentation — they
# would be 125 KB of machine output published to the docs site. They stay in the ignored
# working folder, which is what `.claude/` is for.
WORK = Path(os.environ.get("EVCC_ADAPTER_DOC_WORK") or (ROOT / ".claude" / "generated-docs" / "adapter-config"))
WORK.mkdir(parents=True, exist_ok=True)

PKG = ROOT / "custom_components" / "eufy_vacuum"
CFG_PY = PKG / "adapters" / "config_schema.py"
CAP_PY = PKG / "core" / "capabilities.py"
REG_PY = PKG / "adapters" / "registry.py"
ADAPTER_PY = [
    ("eufy", PKG / "adapters" / "eufy" / "adapter.py"),
    ("roborock", PKG / "adapters" / "roborock" / "adapter.py"),
    # Added 2026-09-13 with the v2.2.0 release switch. A key nobody declares is a
    # contract with no witness, and until this row existed Dreame's declarations were
    # invisible to the reference even though the brand shipped.
    ("dreame", PKG / "adapters" / "dreame" / "adapter.py"),
]
DOC22 = ROOT / "docs" / "dev" / "22-adapter-config-reference.md"
DOC21 = ROOT / "docs" / "dev" / "21-adapter-system.md"
DOCPG = ROOT / "docs" / "contributing" / "porting-guide.md"

SKIP_DIRS = {"__pycache__", ".claude", "node_modules", ".git", "frontend"}


# ---------------------------------------------------------------------------
# ledgers
# ---------------------------------------------------------------------------
@dataclass
class Blind:
    kind: str
    where: str
    detail: str


@dataclass
class Finding:
    cls: str
    where: str
    claim: str
    source_says: str


BLIND: list[Blind] = []
FINDINGS: list[Finding] = []


def blind(kind: str, where: str, detail: str) -> None:
    BLIND.append(Blind(kind, where, detail))


def finding(cls: str, where: str, claim: str, source_says: str) -> None:
    FINDINGS.append(Finding(cls, where, claim, source_says))


def rel(p: Path) -> str:
    try:
        return str(p.relative_to(ROOT)).replace("\\", "/")
    except ValueError:
        return str(p).replace("\\", "/")


def read(p: Path) -> str:
    return p.read_text(encoding="utf-8")


def parse(p: Path) -> ast.Module:
    return ast.parse(read(p), filename=rel(p))


# ---------------------------------------------------------------------------
# 1. module-level binding lookup that handles BOTH Assign and AnnAssign
# ---------------------------------------------------------------------------
def module_binding(tree: ast.Module, name: str) -> ast.expr | None:
    """Module-level value node for `name`, from Assign OR AnnAssign.

    `ADAPTER_CONFIG_SCHEMA: dict[str, dict] = {...}` is an AnnAssign. A walk
    matching only Assign returns None here and every downstream count becomes
    zero -- confidently, silently, and with a precise-looking number.
    """
    for node in tree.body:
        if isinstance(node, ast.Assign):
            for tgt in node.targets:
                if isinstance(tgt, ast.Name) and tgt.id == name:
                    return node.value
        elif isinstance(node, ast.AnnAssign):
            if isinstance(node.target, ast.Name) and node.target.id == name and node.value is not None:
                return node.value
    return None


def any_binding(scope: ast.AST, name: str) -> ast.expr | None:
    """Same, anywhere inside `scope` (Assign OR AnnAssign)."""
    for node in ast.walk(scope):
        if isinstance(node, ast.Assign):
            for tgt in node.targets:
                if isinstance(tgt, ast.Name) and tgt.id == name:
                    return node.value
        elif isinstance(node, ast.AnnAssign):
            if isinstance(node.target, ast.Name) and node.target.id == name and node.value is not None:
                return node.value
    return None


def own_body(fn: ast.AST):
    """Yield nodes belonging to `fn` itself, NOT to functions nested inside it.

    detect_capabilities() defines `_find`, `_find_reg`, `_any_present` and
    `_hint_wins` inside itself. A plain ast.walk picks up their `return`
    statements and their locals; the first version of this script reported four
    phantom "return is not a dict" blind spots because of exactly that.
    """
    nested = (ast.FunctionDef, ast.AsyncFunctionDef, ast.Lambda, ast.ClassDef)
    stack = list(fn.body)
    while stack:
        node = stack.pop()
        yield node
        if isinstance(node, nested):
            # yield the definition itself, but never walk INTO it -- v1 pushed the
            # nested body here and picked up `_find`/`_hint_wins`'s own `return`
            # statements, printing four phantom "return is not a dict" blind spots.
            continue
        stack.extend(ast.iter_child_nodes(node))


# ---------------------------------------------------------------------------
# 2. ADAPTER_CONFIG_SCHEMA
# ---------------------------------------------------------------------------
CFG_TREE = parse(CFG_PY)
CFG_SRC = read(CFG_PY).splitlines()

SCHEMA_NODE = module_binding(CFG_TREE, "ADAPTER_CONFIG_SCHEMA")
if SCHEMA_NODE is None:
    raise SystemExit(
        f"FATAL: ADAPTER_CONFIG_SCHEMA not found in {rel(CFG_PY)}. It is an AnnAssign; a walk "
        "matching only ast.Assign returns nothing here. Refusing to emit a doc from an empty model."
    )
if not isinstance(SCHEMA_NODE, ast.Dict):
    raise SystemExit(f"FATAL: ADAPTER_CONFIG_SCHEMA is a {type(SCHEMA_NODE).__name__}, not a dict literal.")

TOP_LINENO: dict[str, int] = {}
SCHEMA: dict[str, dict] = {}
for k_node, v_node in zip(SCHEMA_NODE.keys, SCHEMA_NODE.values):
    if not (isinstance(k_node, ast.Constant) and isinstance(k_node.value, str)):
        blind("nonliteral-schema-key", rel(CFG_PY),
              f"line {getattr(k_node, 'lineno', '?')}: {ast.unparse(k_node) if k_node else '**expansion'}")
        continue
    key = k_node.value
    TOP_LINENO[key] = k_node.lineno
    try:
        SCHEMA[key] = ast.literal_eval(v_node)
    except (ValueError, SyntaxError) as exc:
        blind("nonliteral-schema-value", rel(CFG_PY), f"{key} (line {k_node.lineno}): {exc}")

BANNERS: list[tuple[int, str]] = []
for i, line in enumerate(CFG_SRC, start=1):
    m = re.match(r"^\s*#\s*=+\s*(.+?)\s*=+\s*$", line)
    if m:
        BANNERS.append((i, m.group(1).strip()))


def banner_for(lineno: int) -> str:
    best = "(unsectioned)"
    for ln, name in BANNERS:
        if ln <= lineno:
            best = name
        else:
            break
    return best


@dataclass
class Entry:
    path: str
    name: str
    parent: str
    kind: str            # "top" | "fields" | "entry_fields"
    type: str
    required: bool
    description: str
    values: list | None
    spec_keys: list[str]
    extra_lists: dict[str, list]   # list-valued spec keys, e.g. canonical_fields
    depth: int


ENTRIES: list[Entry] = []


def walk_schema(d: dict, parent: str = "", kind: str = "top", depth: int = 0) -> None:
    for name, spec in d.items():
        path = f"{parent}.{name}" if parent else name
        if not isinstance(spec, dict):
            blind("nonmapping-schema-entry", rel(CFG_PY), f"{path}: {type(spec).__name__}")
            continue
        ENTRIES.append(Entry(
            path=path, name=name, parent=parent, kind=kind,
            type=str(spec.get("type", "")), required=bool(spec.get("required", False)),
            description=str(spec.get("description", "")), values=spec.get("values"),
            spec_keys=sorted(spec.keys()),
            extra_lists={k: v for k, v in spec.items()
                         if isinstance(v, list) and k not in ("values",)
                         and all(isinstance(x, str) for x in v)},
            depth=depth,
        ))
        for sub, subkind in (("fields", "fields"), ("entry_fields", "entry_fields")):
            if isinstance(spec.get(sub), dict):
                walk_schema(spec[sub], path, subkind, depth + 1)


walk_schema(SCHEMA)
BY_PATH = {e.path: e for e in ENTRIES}
TOP_KEYS = [e.name for e in ENTRIES if e.kind == "top" and e.depth == 0]


def children(path: str, kind: str | None = None) -> list[Entry]:
    return [e for e in ENTRIES if e.parent == path and (kind is None or e.kind == kind)]


def enumerated(path: str) -> set[str]:
    """Every name the schema enumerates directly under `path`."""
    out = {c.name for c in children(path)}
    e = BY_PATH.get(path)
    if e:
        for v in e.extra_lists.values():
            out |= set(v)
    return out


def outer_type(t: str) -> str:
    spec = t.strip()
    for suffix in ("| null", "| none", "|null", "|none"):
        if spec.lower().endswith(suffix):
            spec = spec[: -len(suffix)].strip()
            break
    return spec.split("[", 1)[0].strip()


# blocks declared as a bare DICT with no enumerated interior
OPEN_BLOCKS = sorted(
    e.name for e in ENTRIES
    if e.depth == 0 and outer_type(e.type) == "dict" and not children(e.path)
)
# same, at any depth -- these are the interiors this generator is blind to
OPEN_NESTED = sorted(
    e.path for e in ENTRIES
    if e.depth > 0 and outer_type(e.type) in ("dict", "list") and not children(e.path)
    and not e.extra_lists
)
for name in OPEN_BLOCKS:
    blind("open-ended-block", f"{rel(CFG_PY)} ADAPTER_CONFIG_SCHEMA[{name!r}]",
          "declared as a bare dict with no `fields`/`entry_fields`; its interior is invisible to "
          "this generator AND to the schema walker's unknown-key check")


# ---------------------------------------------------------------------------
# 3. which spec keys does the walker actually ENFORCE?
# ---------------------------------------------------------------------------
def walker_recognised_spec_keys() -> set[str]:
    fn = next((n for n in CFG_TREE.body
               if isinstance(n, ast.FunctionDef) and n.name == "validate_against_schema"), None)
    if fn is None:
        blind("walker-unreadable", rel(CFG_PY),
              "validate_against_schema() not found; cannot derive the enforced spec-key set")
        return set()
    keys: set[str] = set()
    for node in ast.walk(fn):
        if isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute) and node.func.attr == "get":
            if ast.unparse(node.func.value) == "spec" and node.args and isinstance(node.args[0], ast.Constant):
                if isinstance(node.args[0].value, str):
                    keys.add(node.args[0].value)
        if isinstance(node, ast.Subscript) and ast.unparse(node.value) == "spec":
            if isinstance(node.slice, ast.Constant) and isinstance(node.slice.value, str):
                keys.add(node.slice.value)
    return keys


ENFORCED_SPEC_KEYS = walker_recognised_spec_keys()
USED_SPEC_KEYS: dict[str, list[str]] = defaultdict(list)
for e in ENTRIES:
    for sk in e.spec_keys:
        USED_SPEC_KEYS[sk].append(e.path)
DECORATIVE_SPEC_KEYS = {k: v for k, v in USED_SPEC_KEYS.items()
                        if k not in ENFORCED_SPEC_KEYS and k != "description"}

_tf = module_binding(CFG_TREE, "_TYPE_FAMILIES")
TYPE_FAMILY_NAMES: list[str] = []
if isinstance(_tf, ast.Dict):
    TYPE_FAMILY_NAMES = sorted(k.value for k in _tf.keys
                               if isinstance(k, ast.Constant) and isinstance(k.value, str))
else:
    blind("type-families-unreadable", rel(CFG_PY), "_TYPE_FAMILIES is not a readable dict literal")

# _type_ok() strips a "| null" suffix before looking up the family, so the check has
# to strip it too -- v1 did not, and reported `str | null` as an unmapped type.
UNKNOWN_TYPES = sorted({e.type for e in ENTRIES
                        if e.type and outer_type(e.type) not in set(TYPE_FAMILY_NAMES) | {"Any"}})
for t in UNKNOWN_TYPES:
    blind("type-outside-family-map", rel(CFG_PY),
          f"schema type {t!r} has no _TYPE_FAMILIES entry -- _type_ok() returns True unconditionally, "
          f"so the declared type of {', '.join(sorted(e.path for e in ENTRIES if e.type == t)[:4])} "
          "is never actually checked")


# ---------------------------------------------------------------------------
# 4. capabilities.py
# ---------------------------------------------------------------------------
CAP_TREE = parse(CAP_PY)

_khn = module_binding(CAP_TREE, "KNOWN_CAPABILITY_HINTS")
KNOWN_HINTS: set[str] = set()
if _khn is None:
    blind("known-hints-unreadable", rel(CAP_PY), "KNOWN_CAPABILITY_HINTS not found (Assign/AnnAssign)")
else:
    try:
        if isinstance(_khn, ast.Call) and isinstance(_khn.func, ast.Name) and _khn.func.id == "frozenset":
            KNOWN_HINTS = set(ast.literal_eval(_khn.args[0]))
        else:
            KNOWN_HINTS = set(ast.literal_eval(_khn))
    except Exception as exc:
        blind("known-hints-unreadable", rel(CAP_PY), f"not literal-evaluable: {exc}")

DETECT_FN = next((n for n in CAP_TREE.body
                  if isinstance(n, ast.FunctionDef) and n.name == "detect_capabilities"), None)
if DETECT_FN is None:
    raise SystemExit(f"FATAL: detect_capabilities() not found in {rel(CAP_PY)}")

DETECT_RETURN: dict[str, str] = {}
for r in (n for n in own_body(DETECT_FN) if isinstance(n, ast.Return)):
    if isinstance(r.value, ast.Dict):
        for k, v in zip(r.value.keys, r.value.values):
            if isinstance(k, ast.Constant) and isinstance(k.value, str):
                DETECT_RETURN[k.value] = ast.unparse(v)
            else:
                blind("nonliteral-return-key", rel(CAP_PY),
                      f"detect_capabilities return, line {getattr(k, 'lineno', '?')}")
    else:
        blind("detect-return-not-dict", rel(CAP_PY),
              f"line {r.lineno}: return is {type(r.value).__name__}; payload keys unreadable there")

DETECT_SUPPORTS = sorted(k for k in DETECT_RETURN if k.startswith("supports_"))
DETECT_AVAILABLE = sorted(k for k in DETECT_RETURN if k.endswith("_available"))

DETECT_LOCALS: dict[str, str] = {}
for node in own_body(DETECT_FN):
    if isinstance(node, ast.Assign) and len(node.targets) == 1 and isinstance(node.targets[0], ast.Name):
        DETECT_LOCALS[node.targets[0].id] = ast.unparse(node.value)
    elif isinstance(node, ast.AnnAssign) and isinstance(node.target, ast.Name) and node.value is not None:
        DETECT_LOCALS[node.target.id] = ast.unparse(node.value)

HINT_READS: dict[str, str] = {}      # flag -> "permissive" | "authoritative"
HINT_DEFAULTS: dict[str, str] = {}
for node in own_body(DETECT_FN):
    if isinstance(node, ast.Call):
        f = node.func
        if isinstance(f, ast.Attribute) and f.attr == "get" and ast.unparse(f.value) == "_hints":
            if node.args and isinstance(node.args[0], ast.Constant) and isinstance(node.args[0].value, str):
                HINT_READS.setdefault(node.args[0].value, "permissive")
            elif node.args:
                blind("nonliteral-hint-read", rel(CAP_PY),
                      f"line {node.lineno}: _hints.get({ast.unparse(node.args[0])})")
        elif isinstance(f, ast.Name) and f.id == "_hint_wins":
            if node.args and isinstance(node.args[0], ast.Constant) and isinstance(node.args[0].value, str):
                nm = node.args[0].value
                HINT_READS[nm] = "authoritative"
                HINT_DEFAULTS[nm] = ast.unparse(node.args[1]) if len(node.args) > 1 else "(none)"
            elif node.args:
                blind("nonliteral-hint-read", rel(CAP_PY),
                      f"line {node.lineno}: _hint_wins({ast.unparse(node.args[0])})")
    if isinstance(node, ast.Subscript) and ast.unparse(node.value) == "_hints":
        if isinstance(node.slice, ast.Constant) and isinstance(node.slice.value, str):
            HINT_READS.setdefault(node.slice.value, "permissive")

HINTS_READ_BUT_UNDECLARED = sorted(set(HINT_READS) - KNOWN_HINTS)
HINTS_DECLARED_BUT_UNREAD = sorted(KNOWN_HINTS - set(HINT_READS))

CAP_BLOCK_FIELDS = [e.name for e in children("capabilities", "fields")]


# ---------------------------------------------------------------------------
# 5. registry._validate_adapter
# ---------------------------------------------------------------------------
REG_TREE = parse(REG_PY)
VALIDATE_FN = next((n for n in ast.walk(REG_TREE)
                    if isinstance(n, ast.FunctionDef) and n.name == "_validate_adapter"), None)
REG_CHECKED: dict[str, list[int]] = defaultdict(list)
if VALIDATE_FN is None:
    blind("registry-validate-unreadable", rel(REG_PY), "_validate_adapter() not found")
else:
    for node in ast.walk(VALIDATE_FN):
        if isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute) and node.func.attr == "get":
            if ast.unparse(node.func.value) == "config" and node.args and isinstance(node.args[0], ast.Constant):
                if isinstance(node.args[0].value, str):
                    REG_CHECKED[node.args[0].value].append(node.lineno)


# ---------------------------------------------------------------------------
# 6. what the two shipped adapters actually declare
# ---------------------------------------------------------------------------
@dataclass
class AdapterDecl:
    brand: str
    file: str
    top_keys: list[str] = field(default_factory=list)
    capabilities: dict[str, str] = field(default_factory=dict)
    capability_hints: dict[str, str] = field(default_factory=dict)


ADAPTERS: list[AdapterDecl] = []


def dict_pairs(node: ast.expr, tree: ast.Module, where: str, label: str) -> dict[str, str]:
    """Resolve a dict-valued expression to {key: unparsed value}.

    Handles `dict(capability_hints)`: the local it names is itself an AnnAssign
    (`capability_hints: dict[str, bool] = {...}`) -- the same trap as
    ADAPTER_CONFIG_SCHEMA, one scope down.
    """
    if isinstance(node, ast.Dict):
        out: dict[str, str] = {}
        for k, v in zip(node.keys, node.values):
            if isinstance(k, ast.Constant) and isinstance(k.value, str):
                out[k.value] = ast.unparse(v)
            else:
                blind("nonliteral-adapter-key", where, f"{label}: {ast.unparse(k) if k else '**expansion'}")
        return out
    if isinstance(node, ast.Call) and isinstance(node.func, ast.Name) and node.func.id == "dict" and len(node.args) == 1:
        return dict_pairs(node.args[0], tree, where, label)
    if isinstance(node, ast.Name):
        bound = any_binding(tree, node.id)
        if bound is not None and bound is not node:
            return dict_pairs(bound, tree, where, label)
    blind("unresolved-adapter-dict", where, f"{label}: {ast.unparse(node)[:80]}")
    return {}


for brand, path in ADAPTER_PY:
    if not path.exists():
        blind("adapter-missing", rel(path), "shipped adapter file not found")
        continue
    tree = parse(path)
    decl = AdapterDecl(brand=brand, file=rel(path))
    cfg_dicts = [n for n in ast.walk(tree) if isinstance(n, ast.Dict)
                 and any(isinstance(k, ast.Constant) and k.value == "adapter_id" for k in n.keys if k is not None)]
    if not cfg_dicts:
        blind("adapter-config-dict-not-found", rel(path), "no dict literal carrying an 'adapter_id' key")
    for d in cfg_dicts:
        for k, v in zip(d.keys, d.values):
            if isinstance(k, ast.Constant) and isinstance(k.value, str):
                if k.value not in decl.top_keys:
                    decl.top_keys.append(k.value)
                if k.value == "capabilities":
                    decl.capabilities.update(dict_pairs(v, tree, rel(path), "capabilities"))
                if k.value == "capability_hints":
                    decl.capability_hints.update(dict_pairs(v, tree, rel(path), "capability_hints"))
            else:
                blind("nonliteral-adapter-key", rel(path), f"adapter config dict, line {d.lineno}")
    decl.top_keys.sort()
    ADAPTERS.append(decl)

DECLARED_BY: dict[str, list[str]] = defaultdict(list)
for a in ADAPTERS:
    for k in a.top_keys:
        DECLARED_BY[k].append(a.brand)
ADAPTER_TEXT = "\n".join(read(p) for _, p in ADAPTER_PY if p.exists())


# ---------------------------------------------------------------------------
# 7. conservative consumer scan
# ---------------------------------------------------------------------------
CONSUMER_RECV = re.compile(r"(?i)(adapter|_cfg|cfg|config)")
CONSUMERS: dict[str, list[str]] = defaultdict(list)
PKG_TEXT: dict[str, str] = {}
_scanned = 0
for p in sorted(PKG.rglob("*.py")):
    if any(part in SKIP_DIRS for part in p.relative_to(ROOT).parts):
        continue
    _scanned += 1
    src = read(p)
    PKG_TEXT[rel(p)] = src
    try:
        t = ast.parse(src, filename=rel(p))
    except SyntaxError as exc:
        blind("unparseable-module", rel(p), f"SyntaxError: {exc}")
        continue
    for node in ast.walk(t):
        if not isinstance(node, ast.Call):
            continue
        f = node.func
        if isinstance(f, ast.Name) and f.id == "get_adapter_value" and len(node.args) >= 2:
            a = node.args[1]
            if isinstance(a, ast.Constant) and isinstance(a.value, str) and a.value in SCHEMA:
                CONSUMERS[a.value].append(f"{rel(p)}:{node.lineno}")
        elif isinstance(f, ast.Attribute) and f.attr == "get" and node.args:
            a = node.args[0]
            if isinstance(a, ast.Constant) and isinstance(a.value, str) and a.value in SCHEMA:
                recv = ast.unparse(f.value)
                if CONSUMER_RECV.search(recv) and "self.data" not in recv:
                    CONSUMERS[a.value].append(f"{rel(p)}:{node.lineno}")

blind("consumer-scan-conservative", f"{_scanned} package modules",
      "read sites come only from `get_adapter_value(_, \"KEY\")` and "
      "`<expr matching adapter|cfg|config>.get(\"KEY\")`. Any read reached through a helper, a loop "
      "variable, `**kwargs`, or a key held in a constant is INVISIBLE. The per-key consumer lists are "
      "a floor, never a complete set.")


# ---------------------------------------------------------------------------
# 8. doc parsing
# ---------------------------------------------------------------------------
BACKTICK = re.compile(r"`([^`\n]+)`")
IDENT = re.compile(r"^[a-z_][a-z0-9_]*(\.[a-z_][a-z0-9_]*)*$")
WORD = re.compile(r"\b[a-z_][a-z0-9_]{2,}\b")


@dataclass
class Heading:
    level: int
    lineno: int
    raw: str
    key: str | None
    body: str = ""
    body_end: int = 0


def split_fences(text: str) -> tuple[str, str]:
    """(prose, fenced-code) -- BACKTICK regex must never run over a ``` fence.

    v1 did, and the triple-backtick pairs swallowed whole code blocks into one
    fake "identifier", which is why `supports_zone_clean` came back as
    undocumented while sitting in plain sight in the §14 code block.
    """
    prose, code, in_fence = [], [], False
    for line in text.splitlines():
        if line.lstrip().startswith("```"):
            in_fence = not in_fence
            continue
        (code if in_fence else prose).append(line)
    return "\n".join(prose), "\n".join(code)


def mentions(body: str) -> set[str]:
    """Every identifier the section names, in prose backticks or inside a fence.

    Backtick contents are ALSO split into word tokens: the docs write
    `` `zone_max: 10` `` and `` `entities.active_map` ``, so matching the whole
    capture reported five zone caps as undocumented while they sat in plain
    sight. This trades recall for precision deliberately -- see the README.
    """
    prose, code = split_fences(body)
    caps = set(BACKTICK.findall(prose))
    out = set(caps)
    for c in caps:
        out |= set(WORD.findall(c))
    out |= set(WORD.findall(code))
    return out


def doc_headings(text: str) -> list[Heading]:
    lines = text.splitlines()
    hs: list[Heading] = []
    in_fence = False
    for i, line in enumerate(lines, start=1):
        if line.lstrip().startswith("```"):
            in_fence = not in_fence
            continue
        if in_fence:
            continue
        m = re.match(r"^(#{2,4})\s+(.*)$", line)
        if not m:
            continue
        raw = m.group(2).strip()
        key = next((c for c in BACKTICK.findall(raw) if IDENT.match(c)), None)
        hs.append(Heading(level=len(m.group(1)), lineno=i, raw=raw, key=key))
    for idx, h in enumerate(hs):
        end = len(lines)
        for nxt in hs[idx + 1:]:
            if nxt.level <= h.level:
                end = nxt.lineno - 1
                break
        h.body_end = end
        h.body = "\n".join(lines[h.lineno - 1:end])
    return hs


DOC22_TEXT = read(DOC22) if DOC22.exists() else ""
DOC21_TEXT = read(DOC21) if DOC21.exists() else ""
DOCPG_TEXT = read(DOCPG) if DOCPG.exists() else ""
for p, t in ((DOC22, DOC22_TEXT), (DOC21, DOC21_TEXT), (DOCPG, DOCPG_TEXT)):
    if not t:
        blind("doc-missing", rel(p), "target doc not found; every detector against it is inert this run")

H22 = doc_headings(DOC22_TEXT)
DOC22_LINES = DOC22_TEXT.splitlines()

DOC_SECTION: dict[str, Heading] = {}
for h in H22:
    if h.key and h.key in SCHEMA and h.key not in DOC_SECTION:
        DOC_SECTION[h.key] = h


def build_scope_map(headings: list[Heading], nlines: int) -> list[str | None]:
    """Per-line innermost schema path the doc is talking about.

    `### \\`dispatch.phase_timing\\`` scopes to that nested block; a plain
    `### Schema` scopes back to the enclosing top-level block. Without this,
    every table row anywhere in §13 was checked against `dispatch`'s own fields
    -- 18 phantom findings in v1.
    """
    scope: list[str | None] = [None] * (nlines + 2)
    cur_block: str | None = None
    cur_scope: str | None = None
    hs = sorted(headings, key=lambda x: x.lineno)
    for idx, h in enumerate(hs):
        if h.key and h.key in SCHEMA:
            cur_block = cur_scope = h.key
        elif cur_block:
            cand = None
            if h.key:
                if h.key in BY_PATH:
                    cand = h.key
                elif f"{cur_block}.{h.key}" in BY_PATH:
                    cand = f"{cur_block}.{h.key}"
            cur_scope = cand or cur_block
        end = hs[idx + 1].lineno - 1 if idx + 1 < len(hs) else nlines
        for ln in range(h.lineno, min(end, nlines) + 1):
            scope[ln] = cur_scope
    return scope


SCOPE22 = build_scope_map(H22, len(DOC22_LINES))


@dataclass
class DocTable:
    header_line: int
    first_col_label: str
    rows: list[tuple[int, str]]   # (lineno, first-column backticked name)


def doc_tables(lines: list[str]) -> list[DocTable]:
    out: list[DocTable] = []
    in_fence = False
    i = 0
    while i < len(lines):
        line = lines[i]
        if line.lstrip().startswith("```"):
            in_fence = not in_fence
            i += 1
            continue
        if in_fence or not line.lstrip().startswith("|"):
            i += 1
            continue
        if i + 1 >= len(lines) or not re.match(r"^\s*\|[\s:|-]+\|\s*$", lines[i + 1]):
            i += 1
            continue
        label = line.strip().strip("|").split("|")[0].strip().strip("*").strip()
        t = DocTable(header_line=i + 1, first_col_label=label, rows=[])
        j = i + 2
        while j < len(lines) and lines[j].lstrip().startswith("|"):
            m = re.match(r"^\s*\|\s*`([a-z_][a-z0-9_]*)`", lines[j])
            if m:
                t.rows.append((j + 1, m.group(1)))
            j += 1
        out.append(t)
        i = j
    return out


TABLES22 = doc_tables(DOC22_LINES)
FIELD_TABLE_LABELS = {"field", "key", "setting", "name", "sub-key", "flag", "option", "param", "parameter"}


# ===========================================================================
# DETECTORS
# ===========================================================================

# --- D1 key-undocumented ---------------------------------------------------
for key in TOP_KEYS:
    if key not in DOC_SECTION:
        finding("D1 key-undocumented", f"{rel(DOC22)} (no section)",
                f"no `##`/`###` section names top-level key `{key}`",
                f"{rel(CFG_PY)}:{TOP_LINENO.get(key, '?')} declares it "
                f"({'required' if BY_PATH[key].required else 'optional'}, {BY_PATH[key].type})")

# --- D2 doc-invents-key ----------------------------------------------------
for h in H22:
    if h.level != 2 or not h.key or "." in h.key or h.key in SCHEMA:
        continue
    finding("D2 doc-invents-key", f"{rel(DOC22)}:{h.lineno}",
            f"`## {h.raw}` documents `{h.key}` as a top-level block",
            f"ADAPTER_CONFIG_SCHEMA has no key {h.key!r}")

# --- D3 field-undocumented -------------------------------------------------
for parent in TOP_KEYS:
    sec = DOC_SECTION.get(parent)
    if sec is None:
        continue
    named = mentions(sec.body)
    for ch in children(parent):
        if ch.name in named:
            continue
        finding("D3 field-undocumented", f"{rel(DOC22)}:{sec.lineno} (section `{parent}`)",
                f"`{ch.name}` is never named anywhere in the `{parent}` section",
                f"{rel(CFG_PY)} declares `{ch.path}` ({ch.kind}, {ch.type}, "
                f"{'required' if ch.required else 'optional'})")

# --- D4 doc-invents-field --------------------------------------------------
for t in TABLES22:
    if t.first_col_label.lower() not in FIELD_TABLE_LABELS:
        continue
    scope = SCOPE22[t.header_line] if t.header_line < len(SCOPE22) else None
    if not scope:
        continue
    declared = enumerated(scope)
    if not declared:
        blind("field-table-over-open-block", f"{rel(DOC22)}:{t.header_line}",
              f"a '{t.first_col_label}' table documents {len(t.rows)} field(s) under `{scope}`, which the "
              "schema declares as a bare container with no enumerated interior -- nothing to check against")
        continue
    for lineno, nm in t.rows:
        if nm in declared:
            continue
        shipped = re.search(rf'["\']{re.escape(nm)}["\']', ADAPTER_TEXT) is not None
        read_anywhere = any(re.search(rf'["\']{re.escape(nm)}["\']', s) for s in PKG_TEXT.values())
        finding("D4 doc-invents-field", f"{rel(DOC22)}:{lineno}",
                f"table row documents `{nm}` under `{scope}`",
                f"{rel(CFG_PY)} declares no `{scope}.{nm}`; "
                f"shipped by an adapter: {'yes' if shipped else 'no'}; "
                f"the string appears anywhere in the package: {'yes' if read_anywhere else 'no'}")

# --- D5 required-mismatch --------------------------------------------------
REQ_ANNOT = re.compile(r"\*\((required|optional)\b", re.I)
for key, sec in sorted(DOC_SECTION.items()):
    m = REQ_ANNOT.search(sec.raw)
    if m and (m.group(1).lower() == "required") != BY_PATH[key].required:
        finding("D5 required-mismatch", f"{rel(DOC22)}:{sec.lineno}",
                f"heading marks `{key}` *({m.group(1)})*",
                f"{rel(CFG_PY)} declares required={BY_PATH[key].required}")

# --- D6 count-claim-stale --------------------------------------------------
def check_counts(doc: Path, text: str, claims: list[tuple[str, int, str]]) -> None:
    lines = text.splitlines()
    for pattern, computed, label in claims:
        rx = re.compile(pattern)
        hit = False
        for i, line in enumerate(lines, start=1):
            m = rx.search(line)
            if not m:
                continue
            hit = True
            claimed = int(m.group(1))
            if claimed != computed:
                finding("D6 count-claim-stale", f"{rel(doc)}:{i}",
                        f"{label}: doc says {claimed}", f"source computes {computed}")
        if not hit:
            blind("count-claim-not-found", rel(doc),
                  f"pattern for {label!r} matched nothing; that claim is unchecked this run")


# `~N` is an explicit approximation -- checking it as an exact count is pedantry,
# not drift. v1 reported "~20 supports_* flags" against 21 as a finding.
check_counts(DOC21, DOC21_TEXT, [
    (r"It has \*\*(\d+)\*\* top-level keys", len(TOP_KEYS), "ADAPTER_CONFIG_SCHEMA top-level key count"),
    (r"`entities` block \((\d+) keys\)", len(children("entities", "fields")), "entities field count"),
])
check_counts(DOCPG, DOCPG_TEXT, [
    (r"full (\d+)-flag table", len(CAP_BLOCK_FIELDS), "capabilities block field count (porting guide)"),
])

if DOC21_TEXT:
    d21_lines = DOC21_TEXT.splitlines()
    d21_tables = doc_tables(d21_lines)
    anchor_a = next((i for i, l in enumerate(d21_lines, 1) if re.search(r"originally-declared blocks", l)), None)
    anchor_b = next((i for i, l in enumerate(d21_lines, 1) if re.search(r"late-declared blocks", l)), None)

    def table_after(anchor: int | None) -> DocTable | None:
        if anchor is None:
            return None
        return next((t for t in d21_tables if t.header_line > anchor), None)

    ta, tb = table_after(anchor_a), table_after(anchor_b)
    if ta and tb:
        listed = [n for _, n in ta.rows] + [n for _, n in tb.rows]
        missing = sorted(set(TOP_KEYS) - set(listed))
        dupes = sorted({k for k in listed if listed.count(k) > 1})
        invented = sorted(set(listed) - set(TOP_KEYS))
        if missing:
            finding("D6 count-claim-stale", f"{rel(DOC21)}:{ta.header_line}/{tb.header_line}",
                    f"the two block tables enumerate {len(set(listed))} of {len(TOP_KEYS)} top-level keys",
                    f"never listed: {', '.join(missing)}")
        if dupes:
            finding("D6 count-claim-stale", f"{rel(DOC21)}:{ta.header_line}/{tb.header_line}",
                    f"key(s) in both partition tables: {', '.join(dupes)}",
                    "each top-level key belongs to exactly one partition")
        if invented:
            finding("D6 count-claim-stale", f"{rel(DOC21)}:{ta.header_line}/{tb.header_line}",
                    f"block table(s) list {', '.join(invented)}", "not a top-level schema key")
        m1 = re.search(r"The (\d+) originally-declared blocks", DOC21_TEXT)
        m2 = re.search(r"plus \*\*(\d+) late-declared blocks\*\*", DOC21_TEXT)
        for m, t, label in ((m1, ta, "originally-declared"), (m2, tb, "late-declared")):
            if m and int(m.group(1)) != len(t.rows):
                finding("D6 count-claim-stale", rel(DOC21),
                        f"'{m.group(1)} {label} blocks'", f"that table has {len(t.rows)} rows")
        if m1 and m2 and int(m1.group(1)) + int(m2.group(1)) != len(TOP_KEYS):
            finding("D6 count-claim-stale", rel(DOC21),
                    f"partition claims {m1.group(1)} + {m2.group(1)} = {int(m1.group(1)) + int(m2.group(1))}",
                    f"schema has {len(TOP_KEYS)} top-level keys")
    else:
        blind("partition-tables-not-found", rel(DOC21),
              "could not locate the originally/late-declared block tables; that partition is unchecked")

    m = re.search(r"The (nine|ten|eleven|twelve|eight|seven) engine/open-ended blocks \(([^)]*)\)", DOC21_TEXT)
    if m:
        named = sorted(set(re.findall(r"`([a-z_][a-z0-9_]*)`", m.group(2))))
        if named != OPEN_BLOCKS:
            finding("D6 count-claim-stale", rel(DOC21),
                    f"'{m.group(1)} engine/open-ended blocks' names {len(named)}: {', '.join(named)}",
                    f"source has {len(OPEN_BLOCKS)} bare-dict blocks with no enumerated interior: "
                    f"{', '.join(OPEN_BLOCKS)}")
    else:
        blind("count-claim-not-found", rel(DOC21), "open-ended-blocks sentence not matched")

# --- D14 shape-block-incomplete (doc 22 §3 "full shape at a glance") -------
SHAPE_SEC = next((h for h in H22 if h.level == 2 and "full shape" in h.raw.lower()), None)
if SHAPE_SEC is None:
    blind("shape-block-not-found", rel(DOC22), "no 'full shape at a glance' section; D14 inert")
else:
    _, code = split_fences(SHAPE_SEC.body)
    listed = set(re.findall(r'^\s*"([a-z_][a-z0-9_]*)"\s*:', code, re.M))
    for k in TOP_KEYS:
        if k not in listed:
            finding("D14 shape-block-incomplete", f"{rel(DOC22)}:{SHAPE_SEC.lineno} (section 'full shape')",
                    f"the at-a-glance shape omits `{k}`",
                    f"{rel(CFG_PY)}:{TOP_LINENO.get(k, '?')} declares it as a top-level key")
    for k in sorted(listed - set(TOP_KEYS)):
        finding("D14 shape-block-incomplete", f"{rel(DOC22)}:{SHAPE_SEC.lineno} (section 'full shape')",
                f"the at-a-glance shape lists `{k}`", "ADAPTER_CONFIG_SCHEMA has no such top-level key")

# --- D7 cap-flag-drift -----------------------------------------------------
CAP_SEC = DOC_SECTION.get("capabilities")
if CAP_SEC is None:
    blind("capabilities-section-not-found", rel(DOC22), "D7 partially inert")
else:
    named_in_sec = mentions(CAP_SEC.body)
    for fl in sorted(CAP_BLOCK_FIELDS):
        if fl not in named_in_sec:
            finding("D7 cap-flag-drift", f"{rel(DOC22)}:{CAP_SEC.lineno} (section `capabilities`)",
                    f"`{fl}` is never named in the capabilities section",
                    f"{rel(CFG_PY)} declares capabilities.{fl} ({BY_PATH['capabilities.' + fl].type})")
    # names presented INSIDE the section's schema listing that are not schema keys.
    # Restricted to the `### Schema` sub-block: the section's prose deliberately
    # discusses non-flags (v1 reported the doc's own "these are NOT flags" note
    # as three findings).
    schema_sub = next((h for h in H22
                       if h.level == 3 and h.lineno > CAP_SEC.lineno
                       and h.lineno < CAP_SEC.body_end and h.raw.strip().lower() == "schema"), None)
    if schema_sub is None:
        blind("cap-schema-subsection-not-found", rel(DOC22),
              "no `### Schema` under the capabilities section; the invented-flag check is inert")
    else:
        _, code = split_fences(schema_sub.body)
        for nm in sorted(set(WORD.findall(code))):
            if nm in CAP_BLOCK_FIELDS or nm in DETECT_RETURN:
                continue
            finding("D7 cap-flag-drift", f"{rel(DOC22)}:{schema_sub.lineno} (`capabilities` -> Schema)",
                    f"the flag listing names `{nm}`",
                    "it is in neither the `capabilities` schema block nor detect_capabilities()'s return")

_hint_docs = DOC22_TEXT + "\n" + DOC21_TEXT
for hn in sorted(KNOWN_HINTS):
    if hn not in _hint_docs:
        finding("D7 cap-flag-drift", f"{rel(DOC22)} + {rel(DOC21)}",
                f"capability HINT `{hn}` is never named in either doc",
                f"{rel(CAP_PY)} KNOWN_CAPABILITY_HINTS declares it; registry._validate_adapter rejects "
                "any capability_hints key outside that set")

# --- D8 stale-line-citation ------------------------------------------------
CITATION = re.compile(r"([A-Za-z0-9_./]+\.py):(\d+)(?:-(\d+))?")


def symbol_linenos(path: Path) -> dict[str, tuple[int, int]]:
    """def/class names at any nesting + MODULE-LEVEL bindings only.

    v1 indexed every Assign anywhere, so `entities`, `config`, `capabilities`,
    `fields` and `merged` -- ordinary locals -- resolved as "symbols" and
    produced 20+ phantom stale citations.
    """
    try:
        t = ast.parse(read(path), filename=rel(path))
    except (OSError, SyntaxError):
        return {}
    out: dict[str, tuple[int, int]] = {}
    for node in ast.walk(t):
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
            out.setdefault(node.name, (node.lineno, getattr(node, "end_lineno", node.lineno) or node.lineno))
    for node in t.body:
        if isinstance(node, ast.Assign):
            for tgt in node.targets:
                if isinstance(tgt, ast.Name):
                    out.setdefault(tgt.id, (node.lineno, getattr(node, "end_lineno", node.lineno) or node.lineno))
        elif isinstance(node, ast.AnnAssign) and isinstance(node.target, ast.Name):
            out.setdefault(node.target.id, (node.lineno, getattr(node, "end_lineno", node.lineno) or node.lineno))
    return out


SYMCACHE: dict[str, dict[str, tuple[int, int]]] = {}
ALL_PY = [p for p in PKG.rglob("*.py")
          if not any(part in SKIP_DIRS for part in p.relative_to(ROOT).parts)]


def resolve_cited_file(frag: str, context: str) -> tuple[Path | None, str]:
    frag = frag.strip().lstrip("./")
    for c in (PKG / frag, ROOT / frag):
        if c.is_file():
            return c, "path"
    if "/" not in frag:
        # a bare `manager.py` is ambiguous -- the tree has ten. Prefer a longer path
        # naming the same file in the surrounding lines before guessing; the docs
        # wrap, so the qualifying `core/manager.py` is often a line or two above.
        for m in re.finditer(r"([A-Za-z0-9_./]+/" + re.escape(frag) + r")", context):
            for c in (PKG / m.group(1), ROOT / m.group(1)):
                if c.is_file():
                    return c, "nearby qualified path"
        hits = [p for p in ALL_PY if p.name == frag]
        if len(hits) == 1:
            return hits[0], "unique basename"
        return None, f"ambiguous basename ({len(hits)} matches)"
    return None, "unresolved"


CITE_CHECKED = 0
for doc, text in ((DOC22, DOC22_TEXT), (DOC21, DOC21_TEXT)):
    _lines = text.splitlines()
    for i, line in enumerate(_lines, start=1):
        bt_spans = [(m.start(1), m.end(1), m.group(1)) for m in BACKTICK.finditer(line)]
        context = "\n".join(_lines[max(0, i - 5):i])
        for m in CITATION.finditer(line):
            frag, start_s, end_s = m.group(1), m.group(2), m.group(3)
            path, how = resolve_cited_file(frag, context)
            if path is None:
                blind("citation-file-unresolved", f"{rel(doc)}:{i}", f"cited file {frag!r}: {how}")
                continue
            nlines = len(read(path).splitlines())
            start, end = int(start_s), int(end_s) if end_s else int(start_s)
            CITE_CHECKED += 1
            cite = f"{frag}:{start_s}{'-' + end_s if end_s else ''}"
            if start > nlines or end > nlines:
                finding("D8 stale-line-citation", f"{rel(doc)}:{i}",
                        f"cites `{cite}`", f"{rel(path)} has only {nlines} lines")
                continue
            syms = SYMCACHE.setdefault(rel(path), symbol_linenos(path))
            # only the ADJACENT backticked token -- the one the citation annotates.
            # A doc line often names several symbols and cites one of them.
            best = None
            for s, e, txt in bt_spans:
                name = re.sub(r"\(.*", "", txt).strip()
                if name not in syms:
                    continue
                dist = m.start() - e if e <= m.start() else s - m.end()
                if 0 <= dist <= 45 and (best is None or dist < best[0]):
                    best = (dist, name)
            if best is None:
                blind("citation-symbol-unnamed", f"{rel(doc)}:{i}",
                      f"citation `{cite}` has no adjacent resolvable symbol; the range is not checkable")
                continue
            sym = best[1]
            s_lo, s_hi = syms[sym]
            if s_hi < start or s_lo > end:
                finding("D8 stale-line-citation", f"{rel(doc)}:{i}",
                        f"cites `{sym}` at `{cite}`",
                        f"{rel(path)} defines `{sym}` at lines {s_lo}-{s_hi}")

# --- D9 schema-absence-claim-false ----------------------------------------
ABSENT = re.compile(r"schema-absent|absent from\s+`?adapters/config_schema\.py`?|not schema-declared", re.I)
RETRACTED = re.compile(r"(once|previously|formerly|used to be|no longer)\s+schema-absent|also schema-declared", re.I)
for i, line in enumerate(DOC22_LINES, start=1):
    if not ABSENT.search(line) or RETRACTED.search(line):
        continue
    scope = SCOPE22[i] if i < len(SCOPE22) else None
    row = re.match(r"^\s*\|\s*`([a-z_][a-z0-9_]*)`", line)
    if row:
        # a table row: the subject is its own first column, resolved in scope
        nm = row.group(1)
        cand = nm if nm in BY_PATH else (f"{scope}.{nm}" if scope else None)
        subject = cand if cand in BY_PATH else None
        if subject is None:
            continue  # the marker is correct: nothing by that name is declared
    else:
        subject = scope if scope in BY_PATH else None
        if subject is None:
            blind("absence-claim-unattributable", f"{rel(DOC22)}:{i}",
                  "a schema-absence marker sits outside any resolvable schema scope")
            continue
    e = BY_PATH[subject]
    finding("D9 schema-absence-claim-false", f"{rel(DOC22)}:{i}",
            f"marks `{subject}` as schema-absent",
            f"{rel(CFG_PY)} declares it ({e.kind}, {e.type}, "
            f"{'required' if e.required else 'optional'})"
            + (f", line {TOP_LINENO[subject]}" if subject in TOP_LINENO else ""))

# --- D10 consumer-table-incomplete ----------------------------------------
CONSUMER_SEC = next((h for h in H22 if h.level == 2 and "reads each section" in h.raw.lower()), None)
if CONSUMER_SEC is None:
    blind("consumer-table-not-found", rel(DOC22), "no 'where the framework reads each section' section; D10 inert")
else:
    rows = {n for t in doc_tables(CONSUMER_SEC.body.splitlines()) for _, n in t.rows}
    for key in TOP_KEYS:
        if key in rows or not CONSUMERS.get(key):
            continue
        finding("D10 consumer-table-incomplete",
                f"{rel(DOC22)}:{CONSUMER_SEC.lineno} (section 'where the framework reads each section')",
                f"the section-to-consumer table has no row for `{key}`",
                f"a conservative scan finds {len(set(CONSUMERS[key]))} read site(s), e.g. {sorted(set(CONSUMERS[key]))[0]}")
    for ln in CONSUMER_SEC.body.splitlines():
        rm = re.match(r"^\s*\|\s*`([a-z_][a-z0-9_]*)`\s*\|", ln)
        if not rm or rm.group(1) not in SCHEMA:
            continue
        key = rm.group(1)
        cited = set(re.findall(r"`([A-Za-z0-9_/]+\.py)`", ln))
        if not cited:
            continue
        # A module that never contains the QUOTED key literal cannot be doing
        # cfg["KEY"] / cfg.get("KEY"). That containment check is the FP filter: the
        # AST scan alone cannot see a read reached through a helper, so "the scan
        # did not find it" is not evidence. "The string is not in the file" is.
        silent = sorted(c for c in cited
                        if f"custom_components/eufy_vacuum/{c}" in PKG_TEXT
                        and f'"{key}"' not in PKG_TEXT[f"custom_components/eufy_vacuum/{c}"]
                        and f"'{key}'" not in PKG_TEXT[f"custom_components/eufy_vacuum/{c}"])
        if silent:
            found = sorted({c.rsplit(":", 1)[0].split("custom_components/eufy_vacuum/", 1)[-1]
                            for c in CONSUMERS.get(key, [])})
            finding("D15 consumer-row-names-silent-module",
                    f"{rel(DOC22)} 'where the framework reads each section', row `{key}`",
                    f"names {', '.join(silent)} as a consumer of `{key}`",
                    f"that file never contains the quoted literal \"{key}\" or '{key}', so it cannot be "
                    f"reading the block by key"
                    + (f"; the scan finds reads in {', '.join(found)}" if found else ""))

        # D16: the row names a module AND a function inside it. The module-level
        # containment check above passes whenever ANY line of the file mentions the
        # key -- which is how the `capabilities` row survived: capabilities.py has
        # an unrelated `getattr(entry, "capabilities", ...)` 400 lines from the
        # function the row actually names. Narrowing containment to the NAMED
        # FUNCTION'S OWN SPAN is exact and has no such escape hatch.
        for mod in cited:
            full = f"custom_components/eufy_vacuum/{mod}"
            if full not in PKG_TEXT or mod in silent:
                continue
            try:
                mtree = ast.parse(PKG_TEXT[full])
            except SyntaxError:
                continue
            defs = {n.name: (n.lineno, getattr(n, "end_lineno", n.lineno) or n.lineno)
                    for n in ast.walk(mtree)
                    if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef))}
            mlines = PKG_TEXT[full].splitlines()
            for sym in BACKTICK.findall(ln):
                sym = re.sub(r"\(.*", "", sym).strip()
                if sym not in defs or sym.endswith(".py"):
                    continue
                lo, hi = defs[sym]
                span = "\n".join(mlines[lo - 1:hi])
                if f'"{key}"' in span or f"'{key}'" in span:
                    continue
                # Two very different situations look identical here, so separate them.
                # If the function names some OTHER top-level block, the row points at
                # the wrong block -- a category error. If it names no block at all, it
                # is simply handed the already-extracted content by its caller, which
                # is a granularity quibble and not drift. Reporting both as one class
                # buries the first inside six of the second.
                others = sorted(k for k in TOP_KEYS
                                if k != key and (f'"{k}"' in span or f"'{k}'" in span))
                if others:
                    finding("D16 consumer-row-names-wrong-block",
                            f"{rel(DOC22)} 'where the framework reads each section', row `{key}`",
                            f"names `{mod}` (`{sym}`) as the consumer of the `{key}` block",
                            f"`{sym}` (lines {lo}-{hi} of {full}) never contains the literal \"{key}\", "
                            f"though it does carry other block name(s) as literals: "
                            f"{', '.join(chr(96) + k + chr(96) for k in others)}")
                else:
                    blind("consumer-row-symbol-takes-content",
                          f"{rel(DOC22)} row `{key}` -> {mod} ({sym})",
                          f"`{sym}` (lines {lo}-{hi}) names no config block at all; its caller does the "
                          "lookup and hands it the content, so whether the row is right is not "
                          "statically decidable here")

# --- D11 unenforced-spec-key (source-internal) -----------------------------
for sk, paths in sorted(DECORATIVE_SPEC_KEYS.items()):
    finding("D11 unenforced-spec-key", rel(CFG_PY),
            f"schema entries use spec key `{sk}` ({len(paths)}: {', '.join(sorted(paths)[:3])})",
            f"validate_against_schema() reads only {sorted(ENFORCED_SPEC_KEYS)} -- `{sk}` is "
            "documentation, nothing validates it")

# --- D12 hint-contract-drift (source-internal) -----------------------------
for n in HINTS_READ_BUT_UNDECLARED:
    finding("D12 hint-contract-drift", f"{rel(CAP_PY)} detect_capabilities()",
            f"reads capability hint `{n}`",
            "NOT in KNOWN_CAPABILITY_HINTS, so registry._validate_adapter would reject an adapter "
            "declaring it")
for n in HINTS_DECLARED_BUT_UNREAD:
    finding("D12 hint-contract-drift", f"{rel(CAP_PY)} KNOWN_CAPABILITY_HINTS",
            f"declares hint `{n}` as valid",
            "detect_capabilities() never reads it -- declaring it would be a silent no-op")

# --- D13 adapter-ships-undeclared-key --------------------------------------
for a in ADAPTERS:
    for k in a.top_keys:
        if k in SCHEMA or k.startswith("_"):
            continue
        finding("D13 adapter-ships-undeclared-key", a.file,
                f"the {a.brand} adapter ships top-level config key `{k}`",
                f"{rel(CFG_PY)} does not declare it; validate_against_schema() would report an unknown key")
    for k in sorted(a.capabilities):
        if k not in CAP_BLOCK_FIELDS:
            finding("D13 adapter-ships-undeclared-key", a.file,
                    f"the {a.brand} adapter ships `capabilities.{k}`",
                    f"{rel(CFG_PY)} declares no capabilities.{k}")
    for k in sorted(a.capability_hints):
        if KNOWN_HINTS and k not in KNOWN_HINTS:
            finding("D13 adapter-ships-undeclared-key", a.file,
                    f"the {a.brand} adapter ships `capability_hints.{k}`",
                    "not in KNOWN_CAPABILITY_HINTS -- registration flags it as a silent no-op")


# ===========================================================================
# rendering
# ===========================================================================
def cell(s: str) -> str:
    return (s or "").replace("|", "\\|").replace("\n", " ").strip()


def yesno(b: bool) -> str:
    return "yes" if b else "no"


def fmt_values(v) -> str:
    return "" if v is None else ", ".join(f"`{x}`" for x in v)


def field_table(parent: str, kind: str) -> list[str]:
    rows = children(parent, kind)
    if not rows:
        return []
    out = [f"**{'Fields' if kind == 'fields' else 'Per-entry fields'}**", "",
           "| Key | Type | Required | Allowed values | Description |", "|---|---|---|---|---|"]
    for r in rows:
        out.append(f"| `{r.name}` | `{cell(r.type)}` | {yesno(r.required)} | {fmt_values(r.values)} | "
                   f"{cell(r.description)} |")
        for g in children(r.path):
            out.append(f"| `{r.name}.{g.name}` | `{cell(g.type)}` | {yesno(g.required)} | "
                       f"{fmt_values(g.values)} | {cell(g.description)} |")
    out.append("")
    return out


def render_config_reference() -> str:
    L: list[str] = []
    A = L.append
    A("# Adapter configuration reference (generated)")
    A("")
    A(f"Generated from `{rel(CFG_PY)}` (`ADAPTER_CONFIG_SCHEMA`, `validate_against_schema`), "
      f"`{rel(REG_PY)}` (`_validate_adapter`) and the two shipped adapters. Every fact below is "
      "derived from source; nothing is transcribed from the hand-written reference.")
    A("")
    mod_doc = ast.get_docstring(CFG_TREE) or ""
    if mod_doc:
        A("## What this contract is")
        A("")
        for para in mod_doc.strip().split("\n\n"):
            A(para.strip())
            A("")
    A("## At a glance")
    A("")
    desc_n = sum(1 for e in ENTRIES if e.description)
    A("| | |")
    A("|---|--:|")
    A(f"| Top-level keys | {len(TOP_KEYS)} |")
    A(f"| Required top-level keys | {sum(1 for k in TOP_KEYS if BY_PATH[k].required)} |")
    A(f"| Documented entries (all depths) | {len(ENTRIES)} |")
    A(f"| ...carrying a prose `description` | {desc_n} ({round(100 * desc_n / max(1, len(ENTRIES)))}%) |")
    A(f"| Blocks declared as a bare dict (open-ended interior) | {len(OPEN_BLOCKS)} |")
    A(f"| Blocks with an extra registration-time check | {len([k for k in TOP_KEYS if k in REG_CHECKED])} |")
    A("")
    A("**Required:** " + ", ".join(f"`{k}`" for k in TOP_KEYS if BY_PATH[k].required)
      + ". Everything else is optional; each optional block's own description states what the "
        "framework does when it is absent.")
    A("")
    A("**Open-ended blocks** (declared `dict` with no enumerated interior, so the schema walker's "
      "unknown-key check does not apply inside them): " + ", ".join(f"`{k}`" for k in OPEN_BLOCKS) + ".")
    A("")
    A("## Full shape")
    A("")
    A("```python")
    A("{")
    last = None
    for k in TOP_KEYS:
        b = banner_for(TOP_LINENO.get(k, 0))
        if b != last:
            A(f"    # --- {b} ---")
            last = b
        e = BY_PATH[k]
        A(f"    {k!r}: {e.type},".ljust(46) + f"# {'required' if e.required else 'optional'}")
    A("}")
    A("```")
    A("")
    A("## Who declares what")
    A("")
    A("| Block | " + " | ".join(a.brand for a in ADAPTERS) + " |")
    A("|---|" + "---|" * len(ADAPTERS))
    for k in TOP_KEYS:
        A(f"| `{k}` | " + " | ".join("yes" if k in a.top_keys else "-" for a in ADAPTERS) + " |")
    A("")
    never = [k for k in TOP_KEYS if not DECLARED_BY.get(k)]
    if never:
        A("Declared in the schema but shipped by neither adapter: " + ", ".join(f"`{k}`" for k in never) + ".")
        A("")
    A("## Validation")
    A("")
    vfn = next((n for n in CFG_TREE.body
                if isinstance(n, ast.FunctionDef) and n.name == "validate_against_schema"), None)
    if vfn is not None:
        for para in (ast.get_docstring(vfn) or "").strip().split("\n\n"):
            A(para.strip())
            A("")
    A("Spec keys the walker enforces: " + ", ".join(f"`{k}`" for k in sorted(ENFORCED_SPEC_KEYS))
      + ". `description` is documentation only.")
    if DECORATIVE_SPEC_KEYS:
        A("")
        A("Spec keys present in the schema that the walker never reads: "
          + ", ".join(f"`{k}` ({len(v)})" for k, v in sorted(DECORATIVE_SPEC_KEYS.items())) + ".")
    A("")
    A(f"Type families recognised by `_type_ok`: {', '.join('`' + t + '`' for t in TYPE_FAMILY_NAMES)}. "
      "Only the outer container is checked; a trailing `| null` permits `None`; an unrecognised type "
      "string passes unconditionally.")
    A("")
    if REG_CHECKED:
        A("**Extra checks at registration** (`registry._validate_adapter`, beyond the schema walk):")
        A("")
        A("| Block | `_validate_adapter` line(s) |")
        A("|---|---|")
        for k in TOP_KEYS:
            if k in REG_CHECKED:
                A(f"| `{k}` | {', '.join(str(x) for x in sorted(REG_CHECKED[k]))} |")
        A("")
    last = None
    for k in TOP_KEYS:
        e = BY_PATH[k]
        b = banner_for(TOP_LINENO.get(k, 0))
        if b != last:
            A(f"## {b.title()}")
            A("")
            last = b
        A(f"### `{k}`")
        A("")
        A(f"type `{e.type}` - " + ("**required**" if e.required else "optional"))
        A("")
        if e.description:
            A(e.description)
            A("")
        if e.values:
            A(f"Allowed values: {fmt_values(e.values)}")
            A("")
        for lk, lv in sorted(e.extra_lists.items()):
            A(f"`{lk}`: {', '.join('`' + x + '`' for x in lv)}")
            A("")
        L.extend(field_table(k, "fields"))
        L.extend(field_table(k, "entry_fields"))
        who = DECLARED_BY.get(k) or []
        A(f"*Declared by:* {', '.join(who) if who else 'neither shipped adapter'}. "
          f"*Source:* `{rel(CFG_PY)}:{TOP_LINENO.get(k, '?')}`."
          + (f" *Registration check:* `{rel(REG_PY)}:{sorted(REG_CHECKED[k])[0]}`." if k in REG_CHECKED else ""))
        A("")
        cs = sorted(set(CONSUMERS.get(k) or []))
        if cs:
            A(f"*Read sites found by a conservative static scan ({len(cs)}; a floor, not a complete set):* "
              + ", ".join(f"`{c}`" for c in cs[:8]) + (" ..." if len(cs) > 8 else ""))
            A("")
    return "\n".join(L).rstrip() + "\n"


def render_capability_reference() -> str:
    L: list[str] = []
    A = L.append
    A("# Capability flags (generated)")
    A("")
    A(f"Generated from `{rel(CAP_PY)}` (`KNOWN_CAPABILITY_HINTS`, `detect_capabilities`), "
      f"`{rel(CFG_PY)}` (`ADAPTER_CONFIG_SCHEMA['capabilities']`) and `{rel(REG_PY)}` "
      "(`_validate_adapter`).")
    A("")
    A("## Three namespaces, one vocabulary")
    A("")
    A("| Namespace | Enumerated by | Size | Validated at registration | Consumed by |")
    A("|---|---|--:|---|---|")
    cap_consumers = sorted({c.rsplit(':', 1)[0] for c in CONSUMERS.get('capabilities', [])})
    A(f"| `capabilities` config block | `ADAPTER_CONFIG_SCHEMA['capabilities']['fields']` | "
      f"{len(CAP_BLOCK_FIELDS)} | yes - the schema walker checks types and rejects unknown keys | "
      f"{', '.join('`' + c + '`' for c in cap_consumers) or 'no read site found by the conservative scan'} |")
    A(f"| `capability_hints` config block | `KNOWN_CAPABILITY_HINTS` (a different file) | "
      f"{len(KNOWN_HINTS)} | yes - `_validate_adapter` rejects any key outside that frozenset | "
      f"`detect_capabilities()` |")
    A(f"| `detect_capabilities()` return | the return dict literal | {len(DETECT_RETURN)} keys, "
      f"{len(DETECT_SUPPORTS)} of them `supports_*` | n/a (output, not input) | the per-vacuum "
      "capability payload |")
    A("")
    A("The `capabilities` block is fully enumerated in the schema and is never read by "
      "`detect_capabilities()`. The `capability_hints` block is the opposite: the schema declares it as "
      f"a bare `dict` with no `fields`, so the schema walker cannot see inside it; `_validate_adapter` "
      f"checks it instead, against a frozenset that lives in `{rel(CAP_PY)}`. The two share key names "
      "and are different dictionaries with different consumers.")
    A("")
    A("## Config-declarable vs detected-only")
    A("")
    A("| Flag | `capabilities` block | hintable | in detection output | hint rule |")
    A("|---|---|---|---|---|")
    for f_ in sorted(set(CAP_BLOCK_FIELDS) | set(KNOWN_HINTS) | set(DETECT_SUPPORTS)):
        A(f"| `{f_}` | {yesno(f_ in CAP_BLOCK_FIELDS)} | {yesno(f_ in KNOWN_HINTS)} | "
          f"{yesno(f_ in DETECT_RETURN)} | {HINT_READS.get(f_, '-')} |")
    A("")
    only_detected = sorted(f_ for f_ in DETECT_SUPPORTS if f_ not in KNOWN_HINTS and f_ not in CAP_BLOCK_FIELDS)
    only_block = sorted(f_ for f_ in CAP_BLOCK_FIELDS if f_ not in KNOWN_HINTS and f_ not in DETECT_RETURN)
    both = sorted(f_ for f_ in KNOWN_HINTS if f_ in CAP_BLOCK_FIELDS)
    hint_only = sorted(f_ for f_ in KNOWN_HINTS if f_ not in CAP_BLOCK_FIELDS)
    A(f"- **Detected-only ({len(only_detected)})** - emitted by `detect_capabilities()`, declarable in "
      "neither config namespace: " + (", ".join(f"`{x}`" for x in only_detected) or "none") + ".")
    A(f"- **Config-block-only ({len(only_block)})** - declarable in the `capabilities` block, never "
      "emitted by detection and not a valid hint: " + (", ".join(f"`{x}`" for x in only_block) or "none") + ".")
    A(f"- **In both config namespaces ({len(both)})**: " + (", ".join(f"`{x}`" for x in both) or "none") + ".")
    A(f"- **Hint-only ({len(hint_only)})** - a valid `capability_hints` key with no `capabilities` "
      "block counterpart: " + (", ".join(f"`{x}`" for x in hint_only) or "none") + ".")
    A("")
    A("## How each detected flag is derived")
    A("")
    A("`permissive` = hint OR entity presence (`True` from either source is enough). "
      "`authoritative` = `_hint_wins`: an explicit hint overrides the derived default, so a brand can "
      "declare a categorical `False`. `-` = no hint is consulted.")
    A("")
    A("| Flag | Hint rule | Derivation |")
    A("|---|---|---|")
    for f_ in DETECT_SUPPORTS:
        rule = HINT_READS.get(f_, "-")
        deriv = DETECT_LOCALS.get(f_) or DETECT_RETURN.get(f_, "")
        if rule == "authoritative" and f_ in HINT_DEFAULTS:
            deriv = f"hint if declared, else {HINT_DEFAULTS[f_]}"
        A(f"| `{f_}` | {rule} | `{cell(deriv)}` |")
    A("")
    pure = [f_ for f_ in DETECT_SUPPORTS if f_ not in HINT_READS]
    A(f"{len(pure)} of the {len(DETECT_SUPPORTS)} `supports_*` flags consult no hint at all: "
      + ", ".join(f"`{x}`" for x in pure) + ".")
    A("")
    if DETECT_AVAILABLE:
        A("## `supports_*` vs `*_available`")
        A("")
        for para in (ast.get_docstring(DETECT_FN) or "").strip().split("\n\n"):
            A(para.strip())
            A("")
        A("| Flag | Value |")
        A("|---|---|")
        for f_ in DETECT_AVAILABLE:
            A(f"| `{f_}` | `{cell(DETECT_RETURN[f_])}` |")
        A("")
    A("## What the two shipped adapters declare")
    A("")
    A("| Flag | " + " | ".join(f"{a.brand} `capabilities`" for a in ADAPTERS) + " | "
      + " | ".join(f"{a.brand} `capability_hints`" for a in ADAPTERS) + " |")
    A("|---|" + "---|" * (2 * len(ADAPTERS)))
    rows = sorted(set(CAP_BLOCK_FIELDS) | set(KNOWN_HINTS)
                  | {k for a in ADAPTERS for k in a.capabilities}
                  | {k for a in ADAPTERS for k in a.capability_hints})
    for f_ in rows:
        cells = [f"`{cell(a.capabilities[f_])}`" if f_ in a.capabilities else "-" for a in ADAPTERS]
        cells += [f"`{cell(a.capability_hints[f_])}`" if f_ in a.capability_hints else "-" for a in ADAPTERS]
        A(f"| `{f_}` | " + " | ".join(cells) + " |")
    A("")
    A("## The hint contract")
    A("")
    cap_lines = read(CAP_PY).splitlines()
    idx = next((i for i, ln in enumerate(cap_lines) if ln.startswith("KNOWN_CAPABILITY_HINTS")), None)
    if idx is not None:
        doc_lines, j = [], idx - 1
        while j >= 0 and cap_lines[j].startswith("#:"):
            doc_lines.append(cap_lines[j][2:].strip())
            j -= 1
        doc_lines.reverse()
        if doc_lines:
            A(re.sub(r"``([^`]+)``", r"`\1`", " ".join(x for x in doc_lines if x)))
            A("")
    A("Valid hint keys: " + ", ".join(f"`{h}`" for h in sorted(KNOWN_HINTS)) + ".")
    A("")
    return "\n".join(L).rstrip() + "\n"


def render_drift() -> str:
    L: list[str] = []
    A = L.append
    A("# Adapter config + capabilities: drift report")
    A("")
    A(f"Current docs checked: `{rel(DOC22)}`, `{rel(DOC21)}`, `{rel(DOCPG)}`.")
    A("Diagnostic only. No tracked file was modified.")
    A("")
    counts: dict[str, int] = defaultdict(int)
    for f_ in FINDINGS:
        counts[f_.cls] += 1
    A("| class | n |")
    A("|---|--:|")
    for c in sorted(counts):
        A(f"| `{c}` | {counts[c]} |")
    A(f"| **total** | **{len(FINDINGS)}** |")
    A("")
    by_cls: dict[str, list[Finding]] = defaultdict(list)
    for f_ in FINDINGS:
        by_cls[f_.cls].append(f_)
    for c in sorted(by_cls):
        A(f"## {c}")
        A("")
        A("| where | doc claims | source says |")
        A("|---|---|---|")
        for f_ in by_cls[c]:
            A(f"| {cell(f_.where)} | {cell(f_.claim)} | {cell(f_.source_says)} |")
        A("")
    A("## Blind spots")
    A("")
    A("Everything this generator could not resolve statically. A generator that silently drops what it "
      "cannot parse reads as complete and is wrong in bulk while carrying a precise-looking number.")
    A("")
    bcounts: dict[str, int] = defaultdict(int)
    for b in BLIND:
        bcounts[b.kind] += 1
    A("| kind | n |")
    A("|---|--:|")
    for k in sorted(bcounts):
        A(f"| `{k}` | {bcounts[k]} |")
    A(f"| **total** | **{len(BLIND)}** |")
    A("")
    by_kind: dict[str, list[Blind]] = defaultdict(list)
    for b in BLIND:
        by_kind[b.kind].append(b)
    for k in sorted(by_kind):
        A(f"### `{k}`")
        A("")
        A("| where | detail |")
        A("|---|---|")
        for b in sorted(by_kind[k], key=lambda x: (x.where, x.detail)):
            A(f"| {cell(b.where)} | {cell(b.detail)} |")
        A("")
    return "\n".join(L).rstrip() + "\n"


def main() -> int:
    (OUT / "ADAPTER-CONFIG.generated.md").write_text(render_config_reference(), encoding="utf-8", newline="\n")
    (OUT / "CAPABILITY-FLAGS.generated.md").write_text(render_capability_reference(), encoding="utf-8", newline="\n")
    (WORK / "ADAPTER-CONFIG.drift.md").write_text(render_drift(), encoding="utf-8", newline="\n")
    index = {
        "top_level_keys": TOP_KEYS,
        "entries": [{"path": e.path, "kind": e.kind, "type": e.type, "required": e.required,
                     "has_description": bool(e.description), "values": e.values,
                     "spec_keys": e.spec_keys} for e in ENTRIES],
        "open_blocks": OPEN_BLOCKS,
        "open_nested": OPEN_NESTED,
        "enforced_spec_keys": sorted(ENFORCED_SPEC_KEYS),
        "unenforced_spec_keys": {k: sorted(v) for k, v in sorted(DECORATIVE_SPEC_KEYS.items())},
        "capabilities_block_fields": sorted(CAP_BLOCK_FIELDS),
        "known_capability_hints": sorted(KNOWN_HINTS),
        "hint_reads": dict(sorted(HINT_READS.items())),
        "hint_defaults": dict(sorted(HINT_DEFAULTS.items())),
        "detect_return_keys": sorted(DETECT_RETURN),
        "detect_supports": DETECT_SUPPORTS,
        "registration_checked_blocks": {k: sorted(v) for k, v in sorted(REG_CHECKED.items())},
        "adapters": [{"brand": a.brand, "file": a.file, "top_keys": a.top_keys,
                      "capabilities": dict(sorted(a.capabilities.items())),
                      "capability_hints": dict(sorted(a.capability_hints.items()))} for a in ADAPTERS],
        "consumers": {k: sorted(set(v)) for k, v in sorted(CONSUMERS.items())},
        "findings": [{"class": f_.cls, "where": f_.where, "claim": f_.claim,
                      "source_says": f_.source_says} for f_ in FINDINGS],
        "blind_spots": [{"kind": b.kind, "where": b.where, "detail": b.detail} for b in BLIND],
    }
    (WORK / "adapter-config.index.json").write_text(
        json.dumps(index, indent=2, ensure_ascii=False) + "\n", encoding="utf-8", newline="\n")

    print(f"schema: {len(TOP_KEYS)} top-level keys, {len(ENTRIES)} entries, "
          f"{sum(1 for e in ENTRIES if e.description)} with a description")
    print(f"capabilities: block={len(CAP_BLOCK_FIELDS)} hints={len(KNOWN_HINTS)} "
          f"detect_supports={len(DETECT_SUPPORTS)}; line-citations checked={CITE_CHECKED}")
    print("findings:")
    counts: dict[str, int] = defaultdict(int)
    for f_ in FINDINGS:
        counts[f_.cls] += 1
    for c in sorted(counts):
        print(f"  {c}  {counts[c]}")
    print(f"  TOTAL  {len(FINDINGS)}")
    print("blind spots:")
    bcounts: dict[str, int] = defaultdict(int)
    for b in BLIND:
        bcounts[b.kind] += 1
    for k in sorted(bcounts):
        print(f"  {k}  {bcounts[k]}")
    print(f"  BLINDTOTAL  {len(BLIND)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
