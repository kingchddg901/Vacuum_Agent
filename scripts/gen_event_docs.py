#!/usr/bin/env python3
"""Generate `docs/dev/reference/EVENTS.md` — the event bus reference, from source.

    python scripts/gen_event_docs.py

The output is a GENERATED file and is gated: `tests.yml`'s *generated docs* job
fails when the tree's copy is not what this script emits now
(`scripts/check_generated_docs.py`). Never hand-edit the output.

WHY THIS IS GENERATED. Eleven events, 26 fire sites, ~92 payload key slots, spread
over five subsystems, and none of it is declared anywhere — there is no
`services.yaml` for the event bus. Every fact in the reference is the result of an
analysis, which is precisely the kind of fact a hand-written page gets wrong slowly
and invisibly. Reasons still belong in prose: this file states WHAT is fired and
WITH WHAT, never why.

SOURCE OF TRUTH is every `hass.bus.async_fire(...)` call site in
`custom_components/eufy_vacuum/`. Three things have to be resolved from it, and
each one has its own way of being confidently wrong:

  1. THE EVENT NAME. It is BUILT, not literal:
        EVENT_JOB_FINISHED = f"{DOMAIN}_job_finished"        # const.py
     A scan that matches only `ast.Constant` finds exactly ONE event of the
     eleven (`mapping/tracker.py` hardcodes two of its names) and then reports
     the other ten as "documented but never fired" — a confident, catastrophic,
     entirely plausible-looking wrong answer. So `ast.JoinedStr` is resolved
     whenever every hole is itself a resolvable constant, `Assign` AND
     `AnnAssign` are both matched, and constants are looked up in the defining
     module first and package-globally second (several EVENT_* live OUTSIDE
     const.py — `mapping/tracker.py` and `listeners/stall_capture.py`).

  2. THE PAYLOAD. Only half the sites pass a dict literal. The rest pass a local
     name, or a builder call (`job_finished_event_data(...)`), or a dict that is
     mutated after construction (`report["action_taken"] = ...`), or a dict that
     is EXTENDED BY THE CALLER of the firing helper (`payload.update(detail)`
     where `detail` is a keyword argument two frames up). Reading only the
     literal sites yields a payload table that is complete-looking and short.

  3. WHERE SITES DISAGREE. Six of the eleven events are fired from more than one
     place, and the sites do not always build a key the same way. An earlier draft
     kept the first expression it saw and dropped the rest, so 17 slots printed one
     expression as though it were the only one — including `source` and `trigger`,
     which are exactly the keys an automation branches on. Divergent expressions are
     now all printed and marked.

THE GENERATOR DECLARES ITS BLIND SPOTS, in the document itself rather than in a
side report nobody opens. Silence is the failure mode: an analysis that cannot see
a construction site reports absence with total confidence, which is how
`THEME_TOKEN_USAGE.md` once called 135 live theme tokens dead.

WHAT THIS DELIBERATELY DOES NOT DO. The prototype also diffed source against the
three prose docs that describe events. That half is not shipped: its corpus was
three hard-coded files while nine documents mention these events, so "documented
nowhere" meant "not in one of the three I read". Extraction is sound; that
comparison was not.
"""
from __future__ import annotations

import ast
import json
import os
import re
from collections import defaultdict
from dataclasses import dataclass, field
from pathlib import Path

# parents[0]=scripts [1]=repo root.
ROOT = Path(os.environ.get("EVCC_EVT_ROOT") or Path(__file__).resolve().parents[1])
PKG = ROOT / "custom_components" / "eufy_vacuum"
# EVCC_GENDOC_OUT lets the staleness gate render into a scratch directory and diff
# instead of writing over the tracked file and restoring it.
OUT = Path(
    os.environ.get("EVCC_GENDOC_OUT")
    or ROOT / "docs" / "dev" / "reference"
)
OUT.mkdir(parents=True, exist_ok=True)

SKIP_DIRS = {"__pycache__", ".claude", "node_modules", ".git", "frontend"}


# --------------------------------------------------------------------------
# blind-spot ledger
# --------------------------------------------------------------------------
@dataclass
class Blind:
    kind: str
    where: str
    detail: str


BLIND: list[Blind] = []


def blind(kind: str, where: str, detail: str) -> None:
    BLIND.append(Blind(kind, where, detail))


# --------------------------------------------------------------------------
# 1. parse the package
# --------------------------------------------------------------------------
def rel(p: Path) -> str:
    return str(p.relative_to(ROOT)).replace("\\", "/")


FILES = sorted(
    p for p in PKG.rglob("*.py")
    if not any(part in SKIP_DIRS for part in p.relative_to(ROOT).parts)
)
TREES: dict[str, ast.Module] = {}
for _f in FILES:
    try:
        _t = ast.parse(_f.read_text(encoding="utf-8"), filename=rel(_f))
    except SyntaxError as e:  # pragma: no cover
        blind("unparseable-module", rel(_f), f"SyntaxError: {e}")
        continue
    # parent links: needed to find the enclosing function of a fire site and the
    # `if` guards above it. ast gives no upward edges.
    for parent in ast.walk(_t):
        for child in ast.iter_child_nodes(parent):
            child.parent = parent          # type: ignore[attr-defined]
    TREES[rel(_f)] = _t


def unp(node: ast.AST | None) -> str:
    if node is None:
        return "—"
    try:
        return re.sub(r"\s+", " ", ast.unparse(node)).strip()
    except Exception:  # pragma: no cover
        return "?"


def enclosing(node: ast.AST, types: tuple[type, ...]):
    cur = getattr(node, "parent", None)
    while cur is not None:
        if isinstance(cur, types):
            return cur
        cur = getattr(cur, "parent", None)
    return None


# --------------------------------------------------------------------------
# 2. module-level string constants — INCLUDING f-strings
# --------------------------------------------------------------------------
# `EVENT_JOB_FINISHED = f"{DOMAIN}_job_finished"` is an ast.JoinedStr whose one
# hole is a Name bound to another module-level constant. Resolving it is the
# whole ballgame: without it this generator finds 1 event, not 11.
#
# Both Assign and AnnAssign are matched. `NAME: type = {...}` is an AnnAssign,
# and matching only Assign produced a confident wrong answer three separate
# times on 2026-08-15 in the sibling services generator.
STR_CONSTS: dict[str, dict[str, str]] = defaultdict(dict)      # file -> name -> value
STR_SITE: dict[str, dict[str, tuple[int, str]]] = defaultdict(dict)  # file -> name -> (line, how)
STR_GLOBAL: dict[str, list[tuple[str, str]]] = defaultdict(list)     # name -> [(file, value)]

_pending: list[tuple[str, str, ast.expr, int]] = []   # (file, name, value node, line)
for fname, tree in TREES.items():
    for node in tree.body:
        if isinstance(node, ast.Assign) and len(node.targets) == 1 and isinstance(node.targets[0], ast.Name):
            _pending.append((fname, node.targets[0].id, node.value, node.lineno))
        elif isinstance(node, ast.AnnAssign) and isinstance(node.target, ast.Name) and node.value is not None:
            _pending.append((fname, node.target.id, node.value, node.lineno))


def _lookup(name: str, fname: str) -> str | None:
    if name in STR_CONSTS[fname]:
        return STR_CONSTS[fname][name]
    vals = {v for _, v in STR_GLOBAL.get(name, [])}
    if len(vals) == 1:
        return next(iter(vals))
    if len(vals) > 1:
        blind("ambiguous-const", fname, f"`{name}` has {len(vals)} distinct values: {sorted(vals)}")
    return None


def _const_value(node: ast.expr, fname: str) -> tuple[str | None, str]:
    """(value, how). `how` records the resolution for the audit trail."""
    if isinstance(node, ast.Constant) and isinstance(node.value, str):
        return node.value, "string literal"
    if isinstance(node, ast.JoinedStr):
        out: list[str] = []
        for part in node.values:
            if isinstance(part, ast.Constant) and isinstance(part.value, str):
                out.append(part.value)
            elif isinstance(part, ast.FormattedValue):
                if isinstance(part.value, ast.Name):
                    v = _lookup(part.value.id, fname)
                    if v is None:
                        return None, f"f-string hole `{part.value.id}` unresolved"
                    out.append(v)
                else:
                    return None, f"f-string hole `{unp(part.value)}` is not a plain name"
            else:  # pragma: no cover
                return None, "unhandled f-string part"
        return "".join(out), "f-string"
    if isinstance(node, ast.Name):
        v = _lookup(node.id, fname)
        return (v, f"alias of `{node.id}`") if v is not None else (None, f"`{node.id}` unresolved")
    return None, "not a string expression"


# three passes: DOMAIN must land before the f-strings that interpolate it, and
# module iteration order is alphabetical, not dependency order.
for _ in range(3):
    for fname, name, value, line in _pending:
        if name in STR_CONSTS[fname]:
            continue
        v, how = _const_value(value, fname)
        if v is None:
            continue
        STR_CONSTS[fname][name] = v
        STR_SITE[fname][name] = (line, how)
        STR_GLOBAL[name].append((fname, v))

# every EVENT_* constant in the package, resolved or not
EVENT_CONSTS: dict[str, dict] = {}
for fname, name, value, line in _pending:
    if not name.startswith("EVENT_"):
        continue
    v = STR_CONSTS[fname].get(name)
    line_how = STR_SITE[fname].get(name, (line, "?"))
    if v is None:
        blind("event-const-unresolved", fname, f"line {line}: `{name} = {unp(value)}` did not resolve to a string")
    EVENT_CONSTS[f"{fname}:{name}"] = {
        "const": name, "file": fname, "line": line,
        "value": v, "how": line_how[1], "expr": unp(value),
    }


# --------------------------------------------------------------------------
# 3. function/method index — for resolving builder calls
# --------------------------------------------------------------------------
DEFS: dict[str, list[tuple[str, ast.FunctionDef | ast.AsyncFunctionDef]]] = defaultdict(list)
for fname, tree in TREES.items():
    for node in ast.walk(tree):
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            DEFS[node.name].append((fname, node))


def _dict_keys(node: ast.Dict, fname: str, where: str) -> list[tuple[str, str]]:
    out: list[tuple[str, str]] = []
    for k, v in zip(node.keys, node.values):
        if k is None:
            blind("payload-dict-unpack", fname, f"{where}: `**` spread inside a payload dict — its keys are invisible")
            continue
        if isinstance(k, ast.Constant) and isinstance(k.value, str):
            out.append((k.value, unp(v)))
        else:
            blind("payload-dynamic-key", fname, f"{where}: non-literal payload key `{unp(k)}`")
    return out


def def_return_keys(name: str, fname: str, where: str, seen: frozenset[str] = frozenset(),
                    depth: int = 0) -> list[tuple[str, str]] | None:
    """Union of the dict literals a function called `name` can return.

    Follows one-line delegates (`return self.run_plan.get_x(**kwargs)`), which is
    how the manager exposes half of the planning surface.
    """
    if depth > 4:
        blind("builder-recursion", fname, f"{where}: gave up following `{name}` at depth {depth}")
        return None
    if name in seen:
        # `EufyVacuumManager.get_runtime_path_block_report` is a one-line delegate to
        # `RunPlanManager.get_runtime_path_block_report` — same name, different class.
        # The sibling definition supplies the keys, so this is not a failure; it is
        # logged rather than dropped because "the resolver stopped here" is a fact a
        # reader of the ledger is entitled to.
        blind("builder-self-delegate", fname,
              f"{where}: `{name}` delegates to another definition of the same name — "
              "not followed a second time; the keys come from the sibling definition")
        return None
    cands = DEFS.get(name) or []
    if not cands:
        blind("builder-not-found", fname, f"{where}: no `def {name}` anywhere in the package")
        return None
    merged: dict[str, str] = {}
    got_any = False
    for dfile, dnode in cands:
        for rnode in ast.walk(dnode):
            if not isinstance(rnode, ast.Return) or rnode.value is None:
                continue
            # a `return None` guard clause is normal (the builder can decline)
            if isinstance(rnode.value, ast.Constant) and rnode.value.value is None:
                continue
            if isinstance(rnode.value, ast.Dict):
                got_any = True
                for k, v in _dict_keys(rnode.value, dfile, f"{name}() return @{rnode.lineno}"):
                    merged.setdefault(k, v)
            elif isinstance(rnode.value, ast.Call):
                fn = rnode.value.func
                sub = fn.attr if isinstance(fn, ast.Attribute) else (fn.id if isinstance(fn, ast.Name) else None)
                if sub is None:
                    continue
                got = def_return_keys(sub, dfile, f"{name}() delegate", seen | {name}, depth + 1)
                if got:
                    got_any = True
                    for k, v in got:
                        merged.setdefault(k, v)
            elif isinstance(rnode.value, ast.Name):
                blind("builder-returns-name", dfile,
                      f"`{name}()` returns the local `{rnode.value.id}` at line {rnode.lineno} — not followed")
    if not got_any:
        blind("builder-no-dict-return", fname, f"{where}: `{name}()` never returns a dict literal")
        return None
    return sorted(merged.items())


def resolve_call_keys(call: ast.Call, fname: str, where: str) -> tuple[list[tuple[str, str]] | None, str]:
    fn = call.func
    name = fn.attr if isinstance(fn, ast.Attribute) else (fn.id if isinstance(fn, ast.Name) else None)
    if name is None:
        blind("payload-call-shape", fname, f"{where}: cannot name the callee `{unp(fn)}`")
        return None, "unresolved call"
    keys = def_return_keys(name, fname, where)
    return keys, f"builder `{name}()`"


# --------------------------------------------------------------------------
# 4. every async_fire call site
# --------------------------------------------------------------------------
@dataclass
class Variant:
    label: str
    keys: list[tuple[str, str]]
    origin: str


@dataclass
class Site:
    event: str | None
    name_expr: str
    name_how: str
    const: str | None
    file: str
    line: int
    func: str
    cls: str | None
    guards: list[str]
    keys: list[tuple[str, str]] = field(default_factory=list)
    conditional: set[str] = field(default_factory=set)
    variants: list[Variant] = field(default_factory=list)
    payload_how: str = ""
    payload_expr: str = ""


def _func_params(fn: ast.FunctionDef | ast.AsyncFunctionDef) -> set[str]:
    a = fn.args
    return {x.arg for x in (a.posonlyargs + a.args + a.kwonlyargs)} | (
        {a.vararg.arg} if a.vararg else set()) | ({a.kwarg.arg} if a.kwarg else set())


def indirect_variants(fnode, param: str, fname: str) -> list[Variant]:
    """`payload.update(detail)` where `detail` is a parameter.

    The keys are supplied BY THE CALLER. Resolve them by finding every call to
    this function in the package and reading the matching keyword argument. This
    is where `trigger: "error"` / `trigger: "area"` stall payloads come from —
    five payload keys that live two frames above the fire site and that a
    call-site-only scan reports as nonexistent.
    """
    out: list[Variant] = []
    target = fnode.name
    for cfile, ctree in TREES.items():
        for node in ast.walk(ctree):
            if not isinstance(node, ast.Call):
                continue
            fn = node.func
            nm = fn.attr if isinstance(fn, ast.Attribute) else (fn.id if isinstance(fn, ast.Name) else None)
            if nm != target:
                continue
            kws = {k.arg: k.value for k in node.keywords if k.arg}
            if param not in kws:
                continue
            val = kws[param]
            if not isinstance(val, ast.Dict):
                blind("indirect-payload-not-literal", cfile,
                      f"line {node.lineno}: `{target}(..., {param}=...)` is `{unp(val)}`, not a dict literal")
                continue
            # label the variant with the caller's other CONSTANT keywords —
            # `trigger="error"` is exactly the discriminator a consumer branches on
            bits = [f"{k}={v.value!r}" for k, v in sorted(kws.items())
                    if k != param and isinstance(v, ast.Constant) and isinstance(v.value, str)]
            # SYMBOL for the origin, like every other citation this generator emits.
            # These two rows were the last line-based ones in the document, and they
            # point into core/manager.py — the single most-edited file in the repo — so
            # they went stale on commits that never touched an event. Parent links are
            # set on every tree (see the loader), so the same `enclosing()` the fire-site
            # scanner uses works here. Falls back to the line only when a call somehow
            # sits outside any function, where there is no symbol to name.
            _cfn = enclosing(node, (ast.FunctionDef, ast.AsyncFunctionDef))
            _ccls = enclosing(node, (ast.ClassDef,))
            _csym = (f"{_ccls.name}.{_cfn.name}" if _ccls and _cfn
                     else _cfn.name if _cfn else None)
            _corigin = f"{cfile}::{_csym}" if _csym else f"{cfile}:{node.lineno}"
            out.append(Variant(
                label=", ".join(bits) or _corigin,
                keys=_dict_keys(val, cfile, f"{target}({param}=) @{node.lineno}"),
                origin=_corigin,
            ))
    if not out:
        blind("indirect-payload-unresolved", fname,
              f"`{target}()` extends its payload with the parameter `{param}` and no caller passes a dict literal")
    return sorted(out, key=lambda v: (v.label, v.origin))


def resolve_payload(node: ast.expr, fname: str, fnode, site_line: int) -> tuple[
        list[tuple[str, str]], set[str], list[Variant], str]:
    where = f"{fname}:{site_line}"
    if isinstance(node, ast.Dict):
        return _dict_keys(node, fname, where), set(), [], "dict literal at the call site"
    if isinstance(node, ast.Call):
        keys, how = resolve_call_keys(node, fname, where)
        if keys is None:
            return [], set(), [], how + " — UNRESOLVED"
        return keys, set(), [], how
    if isinstance(node, ast.Name):
        if fnode is None:
            blind("payload-no-enclosing-func", fname, f"{where}: `{node.id}` fired at module level")
            return [], set(), [], f"local `{node.id}` — UNRESOLVED"
        var = node.id
        keys: dict[str, str] = {}
        conditional: set[str] = set()
        # key -> [(assigned inside an `if`?, value expression)]. A key is only
        # CONDITIONAL when EVERY assignment to it is guarded. `report["action_taken"]`
        # is written once inside the suppressed-recheck branch and once on the main
        # path; taking the first occurrence marked it conditional and printed the
        # branch's value — wrong twice from one shortcut.
        mutations: dict[str, list[tuple[bool, str]]] = defaultdict(list)
        variants: list[Variant] = []
        how: list[str] = []
        params = _func_params(fnode)
        for stmt in ast.walk(fnode):
            # base:  var = {...}   /   var = builder(...)
            if isinstance(stmt, ast.Assign) and len(stmt.targets) == 1:
                t = stmt.targets[0]
                if isinstance(t, ast.Name) and t.id == var:
                    if isinstance(stmt.value, ast.Dict):
                        for k, v in _dict_keys(stmt.value, fname, where):
                            keys.setdefault(k, v)
                        # NO LINE NUMBER. The variable is already named ("local
                        # `payload`") and the enclosing symbol is in the Location
                        # column, so the line added nothing except a citation that
                        # rots. This one survived the first migration pass and was
                        # caught only by a probe: 12 comment lines inserted at the top
                        # of core/manager.py, regenerate, and the gate still failed on
                        # this single row. A doc that cites 40 symbols and one line
                        # number breaks exactly as often as one citing 41 lines.
                        how.append("dict literal")
                    elif isinstance(stmt.value, ast.Call):
                        got, chow = resolve_call_keys(stmt.value, fname, where)
                        if got:
                            for k, v in got:
                                keys.setdefault(k, v)
                            how.append(chow)
                        else:
                            how.append(chow + " — UNRESOLVED")
                    else:
                        blind("payload-assign-shape", fname,
                              f"{where}: `{var}` is assigned `{unp(stmt.value)}` — not a dict or a call")
                # mutation: var["k"] = ...
                # FLOW-INSENSITIVE, approximated by line order: only mutations
                # textually ABOVE the fire are counted. Two fire sites of the same
                # `report` in one function otherwise get identical key sets.
                if isinstance(t, ast.Subscript) and isinstance(t.value, ast.Name) and t.value.id == var:
                    if stmt.lineno < site_line and isinstance(t.slice, ast.Constant) and isinstance(t.slice.value, str):
                        mutations[t.slice.value].append(
                            (enclosing(stmt, (ast.If,)) is not None, unp(stmt.value)))
                        how.append("mutated in place")
            # extension: var.update(X)
            if (isinstance(stmt, ast.Call) and isinstance(stmt.func, ast.Attribute)
                    and stmt.func.attr == "update" and isinstance(stmt.func.value, ast.Name)
                    and stmt.func.value.id == var and stmt.args):
                arg = stmt.args[0]
                if isinstance(arg, ast.Dict):
                    for k, v in _dict_keys(arg, fname, where):
                        keys.setdefault(k, v)
                    how.append("extended by a literal")
                elif isinstance(arg, ast.Name) and arg.id in params:
                    variants.extend(indirect_variants(fnode, arg.id, fname))
                    how.append(f"extended by the caller via `{arg.id}=`")
                else:
                    blind("payload-update-unresolved", fname,
                          f"{where}: `{var}.update({unp(arg)})` — contents unknown")
        for k, writes in mutations.items():
            unguarded = [e for guarded, e in writes if not guarded]
            keys.setdefault(k, unguarded[0] if unguarded else writes[0][1])
            if not unguarded:
                conditional.add(k)
        if not keys and not variants:
            blind("payload-unresolved", fname, f"{where}: local `{var}` never resolves to a dict")
        return sorted(keys.items()), conditional, variants, f"local `{var}`: " + "; ".join(dict.fromkeys(how) or ["UNRESOLVED"])
    blind("payload-shape", fname, f"{where}: payload expression `{unp(node)}` is not handled")
    return [], set(), [], "UNRESOLVED"


SITES: list[Site] = []
for fname, tree in TREES.items():
    for node in ast.walk(tree):
        if not isinstance(node, ast.Call):
            continue
        fn = node.func
        if not (isinstance(fn, ast.Attribute) and fn.attr == "async_fire"):
            continue
        owner = fn.value
        if not (isinstance(owner, ast.Attribute) and owner.attr == "bus"):
            blind("fire-owner-unknown", fname, f"line {node.lineno}: async_fire on `{unp(owner)}`, not `*.bus`")
            continue
        if not node.args:
            blind("fire-arity", fname, f"line {node.lineno}: async_fire with no positional args")
            continue

        name_node = node.args[0]
        const_name = name_node.id if isinstance(name_node, ast.Name) else (
            name_node.attr if isinstance(name_node, ast.Attribute) else None)
        if isinstance(name_node, ast.Constant) and isinstance(name_node.value, str):
            evt, how = name_node.value, "string literal AT THE CALL SITE"
        elif const_name is not None:
            v = _lookup(const_name, fname)
            if v is None:
                evt, how = None, f"`{const_name}` unresolved"
                blind("unresolved-event-name", fname, f"line {node.lineno}: {how}")
            else:
                src = STR_CONSTS[fname].get(const_name)
                origin = fname if src is not None else (STR_GLOBAL[const_name][0][0] if STR_GLOBAL.get(const_name) else "?")
                evt, how = v, f"`{const_name}` ({origin})"
        else:
            evt, how = None, f"`{unp(name_node)}` is not a name or a literal"
            blind("unresolved-event-name", fname, f"line {node.lineno}: {how}")

        fnode = enclosing(node, (ast.FunctionDef, ast.AsyncFunctionDef))
        cnode = enclosing(node, (ast.ClassDef,))
        guards: list[str] = []
        cur: ast.AST | None = node
        while cur is not None and len(guards) < 3:
            par = getattr(cur, "parent", None)
            if isinstance(par, ast.If) and cur in par.body:
                g = unp(par.test)
                guards.append(g if len(g) <= 110 else g[:107] + "…")
            cur = par

        payload_node = node.args[1] if len(node.args) > 1 else next(
            (k.value for k in node.keywords if k.arg == "event_data"), None)
        if payload_node is None:
            blind("no-payload", fname, f"line {node.lineno}: fired with no event_data")
            keys, cond, variants, phow = [], set(), [], "no payload"
        else:
            keys, cond, variants, phow = resolve_payload(payload_node, fname, fnode, node.lineno)

        SITES.append(Site(
            event=evt, name_expr=unp(name_node), name_how=how, const=const_name,
            file=fname, line=node.lineno,
            func=(fnode.name if fnode else "<module>"), cls=(cnode.name if cnode else None),
            guards=list(reversed(guards)),
            keys=keys, conditional=cond, variants=variants,
            payload_how=phow, payload_expr=unp(payload_node) if payload_node is not None else "—",
        ))

SITES.sort(key=lambda s: (s.event or "~", s.file, s.line))
BY_EVENT: dict[str, list[Site]] = defaultdict(list)
for s in SITES:
    if s.event:
        BY_EVENT[s.event].append(s)
EVENTS = sorted(BY_EVENT)


# --------------------------------------------------------------------------
# 5. the model
# --------------------------------------------------------------------------
def site_all_keys(s: Site) -> set[str]:
    out = {k for k, _ in s.keys}
    for v in s.variants:
        out |= {k for k, _ in v.keys}
    return out


MODEL: dict[str, dict] = {}
for evt in EVENTS:
    sites = BY_EVENT[evt]
    always: set[str] | None = None
    everywhere: set[str] = set()
    # EVERY distinct expression per key, not the first one seen. Six of the eleven
    # events fire from more than one place and the sites do not always build a key
    # the same way; keeping only the first collapsed 17 slots into a single
    # expression printed as though it were the only one. `source` and `trigger` are
    # in that set, and they are exactly what an automation branches on — a reader
    # would have written a condition against a value half the sites never send.
    # Unguarded sites are still listed FIRST, because the suppressed-recheck branch
    # of path_blockers writes `action_taken` a literal the main path does not.
    exprs: dict[str, list[str]] = defaultdict(list)

    def _note(key: str, expr: str) -> None:
        if expr not in exprs[key]:
            exprs[key].append(expr)

    for s in sites:
        base = {k for k, _ in s.keys}
        for k, v in s.keys:
            if k not in s.conditional:
                _note(k, v)
        everywhere |= site_all_keys(s)
        always = base if always is None else (always & base)
    for s in sites:
        for k, v in s.keys:
            _note(k, v)
        for var in s.variants:
            for k, v in var.keys:
                _note(k, v)
    always = always or set()
    # CONDITIONAL means guarded everywhere it appears. Taking the union across
    # sites marked `action_taken` conditional because ONE of the two fire sites
    # sits inside the branch that writes it — the other writes it unconditionally.
    conditional = {
        k for k in everywhere
        if any(k in s.conditional for s in sites)
        and all(k in s.conditional for s in sites if k in {kk for kk, _ in s.keys})
    }
    consts = sorted({c["const"] for c in EVENT_CONSTS.values() if c["value"] == evt})
    MODEL[evt] = {
        "constants": consts,
        # SYMBOL form here too: this feeds the JSON model, and a consumer that
        # round-trips a line number inherits the same staleness.
        "const_sites": sorted(f"{c['file']}::{c['const']}" for c in EVENT_CONSTS.values() if c["value"] == evt),
        "keys": sorted(everywhere),
        "keys_on_every_site": sorted(always),
        "keys_conditional": sorted(conditional),
        "key_exprs": {k: list(exprs.get(k, [])) for k in sorted(everywhere)},
        "sites": [
            {"file": s.file, "line": s.line, "func": s.func, "cls": s.cls,
             "guards": s.guards, "payload_how": s.payload_how,
             "keys": [k for k, _ in s.keys],
             "variants": [{"label": v.label, "keys": [k for k, _ in v.keys], "origin": v.origin}
                          for v in s.variants]}
            for s in sites
        ],
        "modules": sorted({s.file for s in sites}),
    }

UNFIRED_CONSTS = sorted(
    (c for c in EVENT_CONSTS.values() if c["value"] and c["value"] not in BY_EVENT),
    key=lambda c: (c["file"], c["const"]),
)



# a single honest ledger line for the two things this generator structurally cannot do
blind("no-type-inference", "—",
      f"payload value TYPES are not inferred; the reference prints the value EXPRESSION for "
      f"{sum(len(MODEL[e]['keys']) for e in EVENTS)} key slots instead")
blind("firing-conditions-not-derived", "—",
      "the `if` guards printed per site are the enclosing tests only — dedup ledgers, adapter "
      "capability gates and cross-tick state machines that decide whether a site is reached are not modelled")
blind("flow-insensitive-mutation", "—",
      "in-place payload mutations are attributed by LINE ORDER, not control flow — a mutation in a "
      "branch not taken is still counted for any fire site textually below it")

# --------------------------------------------------------------------------
# 6. emit the reference
# --------------------------------------------------------------------------
def md_escape(s: str) -> str:
    return s.replace("|", "\\|")


BANNER = (
    "<!-- GENERATED FILE — DO NOT EDIT BY HAND.\n"
    "     Source of truth: every hass.bus.async_fire() call site in\n"
    "     custom_components/eufy_vacuum/, the EVENT_* constants they name\n"
    "     (f-strings resolved), and the payload builders those call sites reach.\n"
    "     Regenerate after adding, removing or repayloading an event:\n"
    "       python scripts/gen_event_docs.py -->"
)

L: list[str] = [BANNER, "", "# Event Reference", ""]
n_sites = len([s for s in SITES if s.event])
n_keys = sum(len(MODEL[e]["keys"]) for e in EVENTS)
L += [
    "> Generated reference — the facts. The *reasons* live in the prose docs: "
    "[Events](../../advanced/02-events.md) for automation authors, "
    "[HA Integration](../02-ha-integration.md) §7 and "
    "[Job Lifecycle](../06-job-lifecycle.md) §10 for why each one exists. "
    "Regenerate with `python scripts/gen_event_docs.py`; CI fails if this file is "
    "not what the generator emits.",
    "",
    f"The integration fires **{len(EVENTS)} events** on `hass.bus` from **{n_sites} call sites**, "
    f"carrying **{n_keys} payload key slots** ({len({k for e in EVENTS for k in MODEL[e]['keys']})} distinct key names). "
    "Every event name below was resolved from the constant that names it, not read as a literal.",
    "",
    "Listen with the `event` trigger platform; every payload is a plain dict.",
    "",
    "`Payload` is derived, not declared: an event whose every key is an identifier "
    "(`vacuum_entity_id`, `map_id`, `job_id`) tells a consumer only THAT something happened and "
    "must be followed by a state-inspection service call; the rest carry the state in the event "
    "itself. Home Assistant's event bus has no `supports_response` — this is the nearest fact a "
    "caller actually needs, and it is computed from the resolved payload.",
    "",
    "| Event | Constant | Fire sites | Keys | Payload |",
    "|---|---|---|---|---|",
]
IDENTITY_ONLY = {"vacuum_entity_id", "map_id", "job_id"}
for evt in EVENTS:
    m = MODEL[evt]
    bearing = "identity only — pull signal" if set(m["keys"]) <= IDENTITY_ONLY else "carries state"
    L.append(f"| [`{evt}`](#{evt}) | `{', '.join(m['constants']) or '—'}` | {len(m['sites'])} "
             f"| {len(m['keys'])} | {bearing} |")
L.append("")
if UNFIRED_CONSTS:
    L += [
        "An `EVENT_*` constant that nothing fires is listed here rather than above — the name exists, "
        "the event does not:",
        "",
        "| Constant | Defined | Value |",
        "|---|---|---|",
    ]
    for c in UNFIRED_CONSTS:
        # SYMBOL, not a line — same reason as the fired-constant block below.
        L.append(f"| `{c['const']}` | `{c['file']}::{c['const']}` | `{c['value']}` |")
    L.append("")
L += ["---", ""]

for evt in EVENTS:
    m = MODEL[evt]
    L += [f"## {evt}", ""]
    cbits = []
    for c in EVENT_CONSTS.values():
        if c["value"] != evt:
            continue
        # SYMBOL, never a line number. The generator knows the constant's NAME, so
        # emitting `file:123` throws that away and produces a citation that rots on any
        # unrelated edit above it: adding five lines of comment to const.py once made
        # NINE citations in this file wrong at a stroke, and the staleness gate then
        # reported the whole document as drifted. `file.py::SYMBOL` survives every edit
        # that does not rename the symbol — and if it IS renamed, check_doc_citations
        # says so instead of silently pointing at whatever now occupies that line.
        cbits.append(f"`{c['const']}` — `{c['file']}::{c['const']}`, {c['how']} `{md_escape(c['expr'])}`")
    L += ["Constant: " + "; ".join(sorted(cbits)), ""]
    L += [f"Fired from {len(m['sites'])} call site(s) in {len(m['modules'])} module(s): "
          + ", ".join(f"`{x}`" for x in m["modules"]), ""]

    L += ["### Payload", "", "| Key | Present | Value expression |", "|---|---|---|"]
    for k in m["keys"]:
        if k in m["keys_conditional"]:
            present = "conditional"
        elif k in m["keys_on_every_site"]:
            present = "every site"
        else:
            n = sum(1 for s in m["sites"] if k in s["keys"] or any(k in v["keys"] for v in s["variants"]))
            present = f"{n} of {len(m['sites'])} sites"
        variants = m["key_exprs"][k]
        # Print every one. Not "differs by site" — that would claim a semantic
        # difference the generator cannot see. Several of these are the same value
        # reached two ways (`call.data['vacuum_entity_id']` at a service handler,
        # a local `vacuum_entity_id` inside the manager). What is TRUE is that the
        # sites build it differently, and the reader gets to judge.
        expr = " · ".join(f"`{md_escape(x)}`" for x in variants) or "—"
        L.append(f"| `{k}` | {present} | {expr} |")
    L.append("")
    if any(len(m["key_exprs"][k]) > 1 for k in m["keys"]):
        L += [
            "Where a key lists more than one expression, the fire sites build it "
            "differently. That is how the value is OBTAINED, not a claim that the "
            "resulting values differ — types are not inferred.",
            "",
        ]

    var_sites = [s for s in BY_EVENT[evt] if s.variants]
    if var_sites:
        L += ["#### Caller-supplied key groups", "",
              "These keys are not written at the fire site. The firing helper extends its payload with a "
              "dict passed in by its caller, so the set depends on which caller fired it.", "",
              "| Discriminator | Keys | Passed at |", "|---|---|---|"]
        for s in var_sites:
            for v in s.variants:
                L.append(f"| `{md_escape(v.label)}` | {', '.join(f'`{k}`' for k, _ in v.keys)} | `{v.origin}` |")
        L.append("")

    # No separate "Enclosing" column: since the location became `file::symbol` it
    # ENDS with that symbol, and a generated table should not print the same string
    # twice. Two fires in one function are still told apart by their guards, which is
    # the distinction that matters — the line number that used to separate them was
    # the thing rotting.
    L += ["### Fire sites", "", "| Location | Payload built by | Nearest guards |", "|---|---|---|"]
    for s in BY_EVENT[evt]:
        encl = f"{s.cls}.{s.func}" if s.cls else s.func
        g = " ⟶ ".join(f"`{md_escape(x)}`" for x in s.guards) or "—"
        # The fire site's stable name is its ENCLOSING function, which is already the
        # next column — so the location cites that rather than a line that moves every
        # time anything above it changes. This table was the last holdout: 29 of the 40
        # citations in this document were still line-based, and an edit anywhere in
        # core/manager.py shifted four of them at once and failed check_generated_docs
        # on a commit that had nothing to do with events.
        L.append(f"| `{s.file}::{encl}` | {md_escape(s.payload_how)} | {g} |")
    L.append("")

L += [
    "> **Line numbers here are current by construction.** They are regenerated from",
    "> source and CI fails when this file disagrees with the generator, which is the",
    "> only reason a reference is allowed to cite them at all — prose in this repo",
    "> cites symbols precisely because prose has no such mechanism.",
    "",
    "## What this reference cannot see",
    "",
    "Declared rather than omitted. An analysis that cannot see a construction site",
    "reports absence with total confidence: this repo's theme-token trace once called",
    "135 live tokens dead for exactly that reason, and deleting them would have broken",
    "theming everywhere. So every limit of the static pass is listed here, grouped,",
    "with its count.",
    "",
]

BY_KIND: dict[str, list[Blind]] = defaultdict(list)
for b in BLIND:
    BY_KIND[b.kind].append(b)

L += ["| Blind spot | n | What it means for a reader |", "|---|--:|---|"]
for kind in sorted(BY_KIND):
    items = BY_KIND[kind]
    detail = items[0].detail
    L.append(f"| `{kind}` | {len(items)} | {md_escape(detail)} |")
L.append("")
for kind in sorted(BY_KIND):
    items = [b for b in BY_KIND[kind] if b.where != "—"]
    if not items:
        continue
    L += [f"**`{kind}`** — {len(items)} site(s):", ""]
    L += [f"- `{md_escape(b.where)}` — {md_escape(b.detail)}" for b in items]
    L.append("")

(OUT / "EVENTS.md").write_text("\n".join(L) + "\n", encoding="utf-8")

