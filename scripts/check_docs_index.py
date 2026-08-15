#!/usr/bin/env python3
"""Check that every dev doc on disk is reachable from `docs/dev/README.md`.

An index fails by OMISSION, and omission is invisible in prose. A missing table
row leaves a visible hole; a missing clause reads as a complete sentence. So the
one thing nobody notices about the reading-order index is a document that never
got added to it — which is exactly what happened to the whole of `design/`: five
files named in backticks inside one bullet, none of them linked, two of them
created the same week nobody spotted it.

NOT A CI GATE. BY RULE, NOT BY OVERSIGHT.
Wiring this into `tests.yml` would fail every push that adds a doc before the doc
pass runs, which is precisely the friction the 2026-06-12 ruling on
`check_legend_drift.py` exists to prevent. This is a DOC-COMMIT rule: run it when
you commit docs, and at the release doc pass. See `00-disaster-recovery-standard.md`
§5.6.

What it checks — reachability, not prose:

  UNINDEXED  a `.md` under docs/dev/ that README.md never links to. The failure.
  DANGLING   a README link pointing at a file that does not exist.

What it deliberately does NOT check: whether the one-line description is any
good, or still true. That is editorial and a script has no opinion on it.

Scope note — `frontend/` is delegated ON PURPOSE. README links only the hub
(`frontend/architecture-overview.md`) and that hub maps its own set, so the
twenty frontend docs are checked against the HUB rather than against README.
`maintenance/` is excluded from the published site (`exclude_docs` in
mkdocs.yml) and is NAMED in backticks rather than linked, deliberately — a link
would render as an `<a href>` to a page that was never built, and
`mkdocs build --strict` reports that at INFO rather than as a warning, so the
build stays green while every reader of the public site gets a 404.

Run:
  python scripts/check_docs_index.py

Exit code: 0 = every doc reachable, 1 = something is unreachable.
"""
from __future__ import annotations

import pathlib
import re
import sys

ROOT = pathlib.Path(__file__).resolve().parent.parent
DEV = ROOT / "docs" / "dev"
README = DEV / "README.md"
HUB = DEV / "frontend" / "architecture-overview.md"

# Named-not-linked by deliberate rule (see the module docstring).
EXCLUDED_DIRS = ("maintenance/",)

LINK_RE = re.compile(r"\]\(([^)>\s]+?\.md)(?:#[^)]*)?\)")


def links_from(doc: pathlib.Path) -> set[str]:
    """Every relative .md link in `doc`, resolved to a repo-relative posix path."""
    if not doc.exists():
        return set()
    out: set[str] = set()
    for raw in LINK_RE.findall(doc.read_text(encoding="utf-8")):
        if raw.startswith(("http://", "https://", "/")):
            continue
        target = (doc.parent / raw).resolve()
        try:
            out.add(target.relative_to(ROOT).as_posix())
        except ValueError:
            continue  # points outside the repo; not ours to police
    return out


def main() -> int:
    on_disk = {
        p.relative_to(ROOT).as_posix()
        for p in DEV.rglob("*.md")
        if p != README
    }
    reachable = links_from(README) | links_from(HUB)

    def excluded(rel: str) -> bool:
        return any(f"docs/dev/{d}" in rel for d in EXCLUDED_DIRS)

    unindexed = sorted(f for f in on_disk if f not in reachable and not excluded(f))
    dangling = sorted(
        f for f in links_from(README)
        if f.startswith("docs/") and not (ROOT / f).exists()
    )

    checked = len([f for f in on_disk if not excluded(f)])
    print(f"docs/dev: {checked} documents checked "
          f"({len(on_disk) - checked} excluded by rule), "
          f"{len(reachable)} reachable via README + the frontend hub")

    # A checker that measured NOTHING prints exactly what a clean tree prints.
    # Same guard as tests/unit/test_service_declaration_parity.py's `assert checked`:
    # a moved docs/ root or a broken link regex would otherwise read as success.
    if checked < 20 or not reachable:
        print(f"\nGATE IS BROKEN, not clean: found {checked} docs and "
              f"{len(reachable)} links. Expected dozens of each — check that "
              f"{DEV} is still the docs root and that LINK_RE still matches.")
        return 1

    if dangling:
        print(f"\nDANGLING — README links a file that does not exist ({len(dangling)}):")
        for f in dangling:
            print(f"  {f}")

    if unindexed:
        print(f"\nUNINDEXED — on disk, reachable from no index ({len(unindexed)}):")
        for f in unindexed:
            print(f"  {f}")
        print("\nAdd a row/bullet in docs/dev/README.md (or, for a frontend doc, in")
        print("docs/dev/frontend/architecture-overview.md). Naming a file in backticks")
        print("is NOT reachable — that is how all of design/ went missing.")

    if unindexed or dangling:
        return 1
    print("clean — every dev doc is reachable from an index")
    return 0


if __name__ == "__main__":
    sys.exit(main())
