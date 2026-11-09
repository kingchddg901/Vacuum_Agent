#!/usr/bin/env python3
"""Census of `# pragma: no cover` sites that the programme's rule does NOT cover.

    python scripts/pragma_census.py            # the report
    python scripts/pragma_census.py --json     # {path: non_compliant_count}

THE RULE. Coverage may be waived with `# pragma: no cover` for a LOGGER LINE only.
Every other excluded line is excluded from the arithmetic too, so a pragma anywhere
else makes a coverage percentage flattering by exactly as much as it hides — and the
percentage is what the 95%-per-file programme is measured on.

WHY THIS COUNTS BODIES, NOT PRAGMAS. A pragma on a compound statement suppresses the
whole statement. `except Exception:  # pragma: no cover` excludes its entire handler,
so a pragma written to skip one `_LOGGER.exception(...)` can be quietly excluding a
`return`, a `continue`, or an assignment as well. Measured at the time this was
written: 224 pragma sites, 189 of them on an `except`, and of those 97 handlers
contained NO logger call at all — mostly `pass`, `continue`, and real returns.

So a site is COMPLIANT when it is:
  * a logger call on the pragma's own line, or
  * an `except` whose body is logger call(s) and at most a bare/constant `return`
    or `pass` — the rule's allowance in substance rather than in letter.

Everything else is counted. That is a per-file NUMBER, not a verdict on any one site:
several of these are genuinely unreachable handlers whose right answer is a recorded
classification rather than a pragma, and deciding which is which needs per-site
judgement. This exists so the total cannot grow while that judgement happens — the
same reasoning, and the same shape, as `mock_census.py`'s W0 ratchet.
"""
from __future__ import annotations

import ast
import json
import os
import re
import sys
from collections import Counter

ROOT = os.path.join("custom_components", "eufy_vacuum")
PRAGMA = re.compile(r"#\s*pragma:\s*no\s?cover")
#: A logger call's receiver. Kept as a prefix set rather than a loose `.warning(`
#: search, so that `self._notify.warning(...)` is not mistaken for logging.
LOG_RECEIVERS = {"_LOGGER", "LOGGER", "logging", "_log", "log"}


def _is_log_stmt(node: ast.AST) -> bool:
    if not isinstance(node, ast.Expr) or not isinstance(node.value, ast.Call):
        return False
    root = ast.unparse(node.value.func).split(".")[0]
    return root in LOG_RECEIVERS


def _is_inert(node: ast.AST) -> bool:
    """A bare/constant `return`, a `pass`, or an empty container return."""
    if isinstance(node, ast.Pass):
        return True
    if not isinstance(node, ast.Return):
        return False
    if node.value is None or isinstance(node.value, ast.Constant):
        return True
    if isinstance(node.value, (ast.List, ast.Tuple)):
        return not node.value.elts
    if isinstance(node.value, ast.Dict):
        return not node.value.keys
    return False


def _handler_is_log_only(handler: ast.ExceptHandler) -> bool:
    logs = [n for n in handler.body if _is_log_stmt(n)]
    rest = [n for n in handler.body if not _is_log_stmt(n)]
    return bool(logs) and all(_is_inert(n) for n in rest)


def _line_is_log(line: str) -> bool:
    stripped = line.strip()
    for recv in LOG_RECEIVERS:
        if stripped.startswith(recv + "."):
            return True
    return False


def census(root: str = ROOT) -> dict[str, int]:
    """{repo-relative path: count of pragma sites the rule does not cover}."""
    out: dict[str, int] = {}
    for dirpath, dirnames, names in os.walk(root):
        dirnames[:] = [d for d in dirnames if d != "__pycache__"]
        for name in sorted(names):
            if not name.endswith(".py"):
                continue
            path = os.path.join(dirpath, name).replace(os.sep, "/")
            text = open(path, encoding="utf-8").read()
            lines = text.splitlines()
            try:
                tree = ast.parse(text)
            except SyntaxError:
                continue
            log_only_handlers = {
                n.lineno for n in ast.walk(tree)
                if isinstance(n, ast.ExceptHandler) and _handler_is_log_only(n)
            }
            count = 0
            for i, line in enumerate(lines, 1):
                if not PRAGMA.search(line):
                    continue
                if _line_is_log(line) or i in log_only_handlers:
                    continue
                count += 1
            if count:
                out[path] = count
    return out


def _detail(root: str = ROOT):
    rows = []
    for dirpath, dirnames, names in os.walk(root):
        dirnames[:] = [d for d in dirnames if d != "__pycache__"]
        for name in sorted(names):
            if not name.endswith(".py"):
                continue
            path = os.path.join(dirpath, name).replace(os.sep, "/")
            text = open(path, encoding="utf-8").read()
            lines = text.splitlines()
            try:
                tree = ast.parse(text)
            except SyntaxError:
                continue
            handlers = {n.lineno: n for n in ast.walk(tree)
                        if isinstance(n, ast.ExceptHandler)}
            for i, line in enumerate(lines, 1):
                if not PRAGMA.search(line):
                    continue
                if _line_is_log(line):
                    rows.append((path, i, "LOGGER-LINE", True))
                elif i in handlers:
                    ok = _handler_is_log_only(handlers[i])
                    rows.append((path, i, "EXCEPT/log-only" if ok else "EXCEPT/carries-code", ok))
                else:
                    rows.append((path, i, "OTHER", False))
    return rows


def main() -> int:
    counts = census()
    if "--json" in sys.argv:
        print(json.dumps(counts, indent=2, sort_keys=True))
        return 0
    rows = _detail()
    kinds = Counter(r[2] for r in rows)
    total = len(rows)
    ok = sum(1 for r in rows if r[3])
    print("%d `pragma: no cover` site(s) under %s" % (total, ROOT))
    for kind, n in kinds.most_common():
        print("   %-22s %4d" % (kind, n))
    print()
    print("   WITHIN the rule (a logger line, or an except whose body is one): %d" % ok)
    print("   NOT within the rule: %d, across %d file(s)" % (total - ok, len(counts)))
    print()
    for path, n in sorted(counts.items(), key=lambda kv: (-kv[1], kv[0]))[:20]:
        print("   %-62s %3d" % (path.replace(ROOT.replace(os.sep, "/") + "/", ""), n))
    return 0


if __name__ == "__main__":
    sys.exit(main())
