"""trace_route — route evidence, not just outcome evidence.

A green outcome proves success; only the executed ROUTE proves the success used
the intended mechanism (DESIGN-trace-route-tool.md; audit-2 charter §4 delta 7).
Zero source modification: coverage.py records which lines and branches of the
integration actually executed under any command; this tool renders that record
agent-readable and answers the two standing questions:

  run     capture a route:  python tools/trace_route.py run -o route.json -- \
              python -m pytest tests/replay --no-cov
  census  every EXCEPT handler that executed under a green run — the mechanical
          form of "silent degradation paths that conceal failures":
              python tools/trace_route.py census route.json
  diff    routes at two SHAs (run each in its own pinned worktree) — the
          three-path fix review's mechanical half:
              python tools/trace_route.py diff before.json after.json

Limits (state wherever output is used): proves what EXECUTED, never what should
execute; a vanished mechanism still needs architectural history to judge; and
deterministic tracing is NEVER race evidence — races stay uninstrumented.
"""

from __future__ import annotations

import argparse
import ast
import json
import subprocess
import sys
import tempfile
from pathlib import Path

SCOPE = "custom_components/eufy_vacuum"


def cmd_run(out_path: str, command: list[str]) -> int:
    """Run ``command`` under branch coverage scoped to the integration; write the route."""
    with tempfile.TemporaryDirectory() as td:
        datafile = str(Path(td) / ".coverage_route")
        # --source (not --include): the repo's coverage config already sets a
        # source, and coverage ignores --include whenever any source is set.
        env_cmd = [
            sys.executable, "-m", "coverage", "run", "--branch",
            f"--source={SCOPE}", f"--data-file={datafile}",
        ]
        # `coverage run` executes ONE python target; for `python -m pytest ...`
        # style commands, strip the leading interpreter.
        target = command[1:] if command and Path(command[0]).name.startswith("python") else command
        proc = subprocess.run(env_cmd + target)
        json_out = str(Path(td) / "route_raw.json")
        subprocess.run(
            [sys.executable, "-m", "coverage", "json", f"--data-file={datafile}",
             "-o", json_out, "-q"],
            check=True,
        )
        with open(json_out, encoding="utf-8") as f:
            raw = json.load(f)

    route = {
        "command": command,
        "exit_code": proc.returncode,
        "files": {
            path: {
                "executed_lines": info.get("executed_lines", []),
                "missing_lines": info.get("missing_lines", []),
                "executed_branches": info.get("executed_branches", []),
            }
            for path, info in raw.get("files", {}).items()
        },
    }
    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(route, f, indent=1)
    print(f"route written: {out_path} ({len(route['files'])} files, command exit {proc.returncode})")
    return proc.returncode


def _except_handlers(path: Path) -> list[tuple[int, int, str]]:
    """(first_body_line, last_body_line, label) for every except handler in a file."""
    try:
        tree = ast.parse(path.read_text(encoding="utf-8"))
    except (OSError, SyntaxError):
        return []
    out = []
    for node in ast.walk(tree):
        if isinstance(node, ast.ExceptHandler) and node.body:
            label = ast.unparse(node.type) if node.type else "bare except"
            out.append((node.body[0].lineno, node.body[-1].end_lineno or node.body[-1].lineno, label))
    return out


def cmd_census(route_path: str) -> int:
    """List every except handler whose BODY executed — the fallback census."""
    with open(route_path, encoding="utf-8") as f:
        route = json.load(f)
    hits = []
    for rel, info in route["files"].items():
        executed = set(info.get("executed_lines", []))
        src = Path(rel)
        if not src.exists():
            continue
        for start, end, label in _except_handlers(src):
            fired = sorted(executed & set(range(start, end + 1)))
            if fired:
                hits.append((rel, start, label, fired[0]))
    if not hits:
        print("census: no except handler executed in scope")
        return 0
    print(f"census: {len(hits)} except handler(s) EXECUTED under this run "
          f"(command exit {route.get('exit_code')}) — each is a degraded path the outcome hid:")
    for rel, line, label, first in sorted(hits):
        print(f"  {rel}:{line}  except {label}")
    return 0


def cmd_diff(before_path: str, after_path: str) -> int:
    """Line-level route diff: what stopped executing, what started."""
    routes = []
    for p in (before_path, after_path):
        with open(p, encoding="utf-8") as f:
            routes.append(json.load(f))
    before, after = routes
    all_files = sorted(set(before["files"]) | set(after["files"]))
    any_change = False
    for rel in all_files:
        b = set(before["files"].get(rel, {}).get("executed_lines", []))
        a = set(after["files"].get(rel, {}).get("executed_lines", []))
        stopped, started = sorted(b - a), sorted(a - b)
        if stopped or started:
            any_change = True
            print(f"{rel}")
            if stopped:
                print(f"  no longer executed: {_ranges(stopped)}")
            if started:
                print(f"  newly executed:     {_ranges(started)}")
    if not any_change:
        print("routes identical — same lines executed on both sides")
    print("\nread with delta-7 discipline: 'intended branch no longer reached while the "
          "output still passes' is the partial-closure signature.")
    return 0


def _ranges(lines: list[int]) -> str:
    out, start, prev = [], None, None
    for n in lines:
        if start is None:
            start = prev = n
        elif n == prev + 1:
            prev = n
        else:
            out.append(f"{start}-{prev}" if prev != start else str(start))
            start = prev = n
    if start is not None:
        out.append(f"{start}-{prev}" if prev != start else str(start))
    return ", ".join(out)


def main() -> int:
    ap = argparse.ArgumentParser(prog="trace_route")
    sub = ap.add_subparsers(dest="mode", required=True)
    p_run = sub.add_parser("run")
    p_run.add_argument("-o", "--out", required=True)
    p_run.add_argument("command", nargs=argparse.REMAINDER,
                       help="command to trace (prefix with --)")
    p_cen = sub.add_parser("census")
    p_cen.add_argument("route")
    p_diff = sub.add_parser("diff")
    p_diff.add_argument("before")
    p_diff.add_argument("after")
    args = ap.parse_args()
    if args.mode == "run":
        cmd = [c for c in args.command if c != "--"]
        if not cmd:
            ap.error("no command given after --")
        return cmd_run(args.out, cmd)
    if args.mode == "census":
        return cmd_census(args.route)
    return cmd_diff(args.before, args.after)


if __name__ == "__main__":
    sys.exit(main())
