#!/usr/bin/env python3
"""Differential equivalence check for the test-factory refactor.

Prove a factored CLONE tests the same behaviour as its untouched ORIGINAL before
the clone is ever allowed near the live suite. Three checks, all must hold:

  1. same set of test names      (no test dropped, renamed, or added)
  2. both fully green, same count
  3. identical executed-line set on the module(s) under test
     (the objective proof that the clone exercises the same code paths — a
     factory that skips a branch the inline code hit shows up right here)

Run inside the test container (pytest + the package import cleanly there):

    docker run --rm -v "<repo>:/workspace" -w /workspace eufy-vacuum-test \\
        python scripts/diff_test_equiv.py <original> <clone> \\
            --cov custom_components/eufy_vacuum/switch.py

Exit 0 + "=> EQUIVALENT" iff all three pass; non-zero + a diff otherwise.
"""

from __future__ import annotations

import argparse
import json
import re
import subprocess
import sys
import tempfile
from pathlib import Path


def _collect_names(path: str) -> set[str]:
    """The set of test node names (``function[+params]``) in a file, file-prefix stripped."""
    out = subprocess.run(
        ["python", "-m", "pytest", path, "--co", "-q", "-p", "no:cacheprovider"],
        capture_output=True, text=True,
    ).stdout
    return {ln.split("::", 1)[1].strip() for ln in out.splitlines() if "::" in ln}


def _norm(mod: str) -> str:
    """Normalise a --cov arg (dotted or path) to a '/'-path stem for matching."""
    stem = mod.replace("\\", "/").removesuffix(".py").rstrip("/")
    return stem if "/" in stem else stem.replace(".", "/")


def _run(path: str, cov_modules: list[str]) -> tuple[bool, int, dict[str, set[int]]]:
    """Run the file under coverage. Return (all_green, passed_count, {file: executed_lines})."""
    cov_json = tempfile.NamedTemporaryFile(suffix=".json", delete=False).name
    cmd = [
        "python", "-m", "pytest", path, "-p", "no:cacheprovider", "-q",
        "--cov-branch", f"--cov-report=json:{cov_json}",
    ]
    cmd += [f"--cov={m}" for m in cov_modules]
    proc = subprocess.run(cmd, capture_output=True, text=True)
    text = proc.stdout + proc.stderr
    green = proc.returncode == 0 and " failed" not in text and " error" not in text
    mobj = re.search(r"(\d+) passed", text)
    count = int(mobj.group(1)) if mobj else 0

    stems = [_norm(m) for m in cov_modules]
    lines: dict[str, set[int]] = {}
    for fp, entry in json.loads(Path(cov_json).read_text()).get("files", {}).items():
        fp_norm = fp.replace("\\", "/")
        if any(stem in fp_norm.removesuffix(".py") for stem in stems):
            lines[fp_norm] = set(entry.get("executed_lines", []))
    Path(cov_json).unlink(missing_ok=True)
    return green, count, lines


def main() -> int:
    ap = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter
    )
    ap.add_argument("original")
    ap.add_argument("clone")
    ap.add_argument("--cov", action="append", default=[], dest="cov", metavar="MODULE",
                    help="module under test (dotted or path); repeatable")
    args = ap.parse_args()

    ok = True

    names_o, names_c = _collect_names(args.original), _collect_names(args.clone)
    if names_o == names_c:
        print(f"OK   same {len(names_o)} test names")
    else:
        ok = False
        print("FAIL test names differ")
        if names_o - names_c:
            print("       only in original:", sorted(names_o - names_c))
        if names_c - names_o:
            print("       only in clone:   ", sorted(names_c - names_o))

    green_o, n_o, cov_o = _run(args.original, args.cov)
    green_c, n_c, cov_c = _run(args.clone, args.cov)
    if green_o and green_c and n_o == n_c:
        print(f"OK   both green, {n_o} passed each")
    else:
        ok = False
        print(f"FAIL outcomes differ: original(green={green_o}, n={n_o}) "
              f"vs clone(green={green_c}, n={n_c})")

    if not args.cov:
        print("WARN no --cov module given; coverage equivalence skipped")
    else:
        files = sorted(set(cov_o) | set(cov_c))
        if not files:
            ok = False
            print("FAIL no coverage captured for the target module(s) — check --cov")
        cov_ok = True
        for fp in files:
            lo, lc = cov_o.get(fp, set()), cov_c.get(fp, set())
            if lo != lc:
                cov_ok = ok = False
                print(f"FAIL coverage differs in {fp}")
                if lo - lc:
                    print("       lines only original hit:", sorted(lo - lc))
                if lc - lo:
                    print("       lines only clone hit:   ", sorted(lc - lo))
        if cov_ok and files:
            print(f"OK   identical executed lines on {len(files)} target file(s)")

    print("\n=> EQUIVALENT" if ok else "\n=> NOT EQUIVALENT")
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
