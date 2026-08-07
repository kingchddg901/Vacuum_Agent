"""Ablation sandbox generator — rule 10 of PROTOCOL-dr-prose-ablation.

Builds the BLIND BUILDER's entire world: a directory containing the candidate
trimmed DR section, a build brief, and the integration tree WITH THE TARGET
REMOVED — and nothing else. No docs/, no tests/, no .claude/, no .git/, no
src/ (frontend), no scripts/. An isolated worktree is NOT blind (the target
and its tests are one grep away); this constructed directory is the boundary.

Callers of the target remain present deliberately: call sites are the public
contract a real disaster-recovery implementer would legitimately have. The
reviewer's coupling scan (rule 4) polices what the PROSE carries; the
incidental-similarity scan (rule 11) polices what the reconstruction carries.

Usage:
    python .claude/notes/_ablation_sandbox.py \
        --repo <repo-root> --out <sandbox-dir> \
        --target custom_components/eufy_vacuum/core/error_tracker.py \
        --section <trimmed-section.md>

Writes the sandbox plus MANIFEST.json (what was included/removed — a forensic
artifact for rule-11 audits). Refuses a non-empty --out.
"""

from __future__ import annotations

import argparse
import json
import os
import shutil
import sys

EXCLUDE_TOP = {"docs", "tests", "scripts", "src", "dist", "harness", "gallery",
               ".claude", ".git", ".github", "node_modules"}
EXCLUDE_ANY = {"__pycache__", ".pytest_cache", ".ruff_cache"}

BRIEF = """# BUILD BRIEF — blind disaster-recovery reconstruction

The file(s) listed in MANIFEST.json under "removed_targets" have been LOST.
Your job: reconstruct them so the integration in this directory works again,
using ONLY what this directory contains.

Your specification is DR-SECTION.md — the disaster-recovery documentation for
the lost subsystem. The surrounding code (its callers, its dependencies, the
adapter configs) is the integration surface your reconstruction must satisfy.

Rules (they are the experiment — violating them voids the run):
- Use ONLY this directory. Do not read, search, fetch, or recall anything
  outside it: no repository checkouts, no web, no memory of "how this project
  does things" beyond what is written here.
- Do not invent tests and do not look for the project's tests; they are not
  here. Examination happens elsewhere, by someone else.
- Write the reconstruction at the exact removed path(s).
- Where DR-SECTION.md is silent, make the choice a competent HA-integration
  developer would make from the visible contracts — do not pad defensively to
  cover meanings you cannot find stated.

Deliverable: the reconstructed file(s), plus RECONSTRUCTION-NOTES.md listing
every decision you had to make that the DR section did NOT determine (these
notes are evidence for the review stage — honest gaps help you, invented
certainty does not).
"""


def build(repo: str, out: str, targets: list[str], section: str) -> None:
    if os.path.exists(out) and os.listdir(out):
        sys.exit(f"refusing: --out {out} exists and is not empty")
    os.makedirs(out, exist_ok=True)

    copied: list[str] = []
    removed: list[str] = []
    norm_targets = {t.replace("\\", "/") for t in targets}

    root = os.path.join(repo, "custom_components")
    for dirpath, dirnames, filenames in os.walk(root):
        dirnames[:] = [d for d in dirnames if d not in EXCLUDE_ANY]
        for fname in filenames:
            src_path = os.path.join(dirpath, fname)
            rel = os.path.relpath(src_path, repo).replace("\\", "/")
            if rel in norm_targets:
                removed.append(rel)
                continue
            dest = os.path.join(out, rel)
            os.makedirs(os.path.dirname(dest), exist_ok=True)
            shutil.copy2(src_path, dest)
            copied.append(rel)

    missing = norm_targets - set(removed)
    if missing:
        shutil.rmtree(out)
        sys.exit(f"refusing: targets not found in repo: {sorted(missing)}")

    shutil.copy2(section, os.path.join(out, "DR-SECTION.md"))
    with open(os.path.join(out, "BUILD-BRIEF.md"), "w", encoding="utf-8") as fh:
        fh.write(BRIEF)
    with open(os.path.join(out, "MANIFEST.json"), "w", encoding="utf-8") as fh:
        json.dump(
            {
                "removed_targets": sorted(removed),
                "section_source": os.path.basename(section),
                "excluded_toplevel": sorted(EXCLUDE_TOP),
                "copied_count": len(copied),
            },
            fh,
            indent=1,
        )
    print(f"sandbox: {out} ({len(copied)} files, {len(removed)} target(s) removed)")


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--repo", required=True)
    ap.add_argument("--out", required=True)
    ap.add_argument("--target", action="append", required=True)
    ap.add_argument("--section", required=True)
    a = ap.parse_args()
    build(a.repo, a.out, a.target, a.section)


if __name__ == "__main__":
    main()
