"""README.md link integrity — the project's front page is not covered by anything else.

WHY THIS FILE EXISTS. ``mkdocs.yml`` sets ``docs_dir: docs`` and builds with
``--strict``, so every link inside ``docs/`` is validated on every Pages build.
``README.md`` is at the repository ROOT, which puts it outside that gate entirely:
no CI job of any kind reads it. A link in it can rot for months without anything
noticing, and it is the first page a stranger sees.

That is not hypothetical. The README pointed at
``…/docs/dev/27-render-harness/`` after the file was renamed to
``docs/dev/frontend/render-harness.md``; the site has no redirects plugin and the
Pages deploy replaces the whole artifact, so the link had been a hard 404 since
the rename. It was found by a manual audit, which is exactly the thing that does
not run on a schedule.

WHAT THIS CHECKS — only what it can check honestly, offline and without network:

[RL-1] every repo-relative path the README references exists on disk;
[RL-2] every published docs-site URL maps to a real source file under ``docs/``;
[RL-3] every in-page anchor matches a heading that is actually present;
[RL-4] every reference-style link definition is used, and every use is defined.

NOT checked: external URLs (network, and other people's repos are allowed to move
out from under us) and whether an image LOOKS right. A green run here means every
link resolves, not that the prose around it is true.
"""

from __future__ import annotations

import re
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[2]
README = REPO_ROOT / "README.md"

#: The published docs site. A URL under this prefix is served from docs/<path>.md,
#: so it can be resolved offline against the source tree rather than over the wire.
DOCS_SITE_PREFIX = "https://kingchddg901.github.io/Vacuum_Agent/"

#: Site paths that are generated rather than authored from a docs/ source file —
#: the site root itself and the two harness-built galleries.
GENERATED_SITE_PATHS = {"", "themes/", "animals/"}


@pytest.fixture(scope="module")
def readme() -> str:
    return README.read_text(encoding="utf-8")


def _inline_targets(text: str) -> list[str]:
    """Every inline link/image target: ``[label](target)`` and ``![alt](target)``."""
    return [m.group(1).strip() for m in re.finditer(r"!?\[[^\]]*\]\(([^)\s]+)", text)]


def _reference_definitions(text: str) -> dict[str, str]:
    """Reference-style definitions at the bottom: ``[name]: url``."""
    return {
        m.group(1).lower(): m.group(2).strip()
        for m in re.finditer(r"^\[([^\]]+)\]:\s*(\S+)", text, re.MULTILINE)
    }


def _reference_uses(text: str) -> set[str]:
    """Reference-style USES — any ``][name]``.

    Matched on the CLOSING bracket rather than as ``[label][name]``, because the
    badge rows nest: ``[![HACS Default][hacs-badge]][hacs-url]``. A pattern that
    tries to span the label cannot match the outer link, since the label itself
    contains brackets — which silently reports every ``*-url`` definition as
    unused.
    """
    return {
        m.group(1).lower()
        for m in re.finditer(r"\]\[([^\]\[]+)\]", text)
    }


def _headings_as_anchors(text: str) -> set[str]:
    """GitHub's heading slugs: lowercase, punctuation dropped, spaces to hyphens."""
    anchors = set()
    for m in re.finditer(r"^#{1,6}\s+(.*)$", text, re.MULTILINE):
        title = m.group(1).strip()
        title = re.sub(r"[`*_]", "", title)                 # strip inline markup
        slug = re.sub(r"[^\w\s-]", "", title).strip().lower()
        anchors.add(re.sub(r"[\s]+", "-", slug))
    return anchors


def test_readme_exists():
    """[RL-0] Guard the guard: if the path is wrong, everything below passes vacuously."""
    assert README.is_file(), f"README.md not found at {README}"
    assert README.stat().st_size > 0


def test_every_local_path_resolves(readme):
    """[RL-1] Repo-relative links and images must exist on disk.

    This is the class that breaks when a screenshot is renamed or retired — the
    README keeps rendering, with a broken-image icon nobody sees until a stranger
    opens the page.
    """
    missing = []
    for target in _inline_targets(readme):
        if target.startswith(("http://", "https://", "#", "mailto:")):
            continue
        path = (REPO_ROOT / target.split("#", 1)[0]).resolve()
        if not path.exists():
            missing.append(target)
    assert not missing, f"README references paths that do not exist: {sorted(set(missing))}"


def test_every_docs_site_url_has_a_source_file(readme):
    """[RL-2] A published docs URL must map to a real file under docs/.

    The site is built from docs/ with --strict and deployed as a whole artifact,
    so a URL with no source file is a hard 404 the moment it deploys. Resolved
    offline against the source tree: no network, no flake.
    """
    targets = _inline_targets(readme) + list(_reference_definitions(readme).values())
    broken = []
    for url in targets:
        if not url.startswith(DOCS_SITE_PREFIX):
            continue
        rel = url[len(DOCS_SITE_PREFIX):].split("#", 1)[0]
        if rel in GENERATED_SITE_PATHS:
            continue
        # mkdocs serves docs/a/b.md at /a/b/ — undo the directory-URL form.
        # The docs artifact is mounted at /docs on the Pages site (the workflow
        # downloads it to public/docs), so every docs URL carries that prefix on
        # top of the path mkdocs generates. Strip it -- including the bare
        # ".../docs/" root, which rstrip leaves as exactly "docs".
        stem = rel.rstrip("/")
        if stem == "docs":
            stem = ""
        elif stem.startswith("docs/"):
            stem = stem[len("docs/"):]
        docs = REPO_ROOT / "docs"
        # A page URL maps to <stem>.md. A DIRECTORY url (the site root, or a
        # section landing like /docs/dev/) maps to that directory's index --
        # which in this tree is README.md, not index.md, for every section.
        resolved = (
            (docs / f"{stem}.md").is_file()
            or (stem == "" and (docs / "index.md").is_file())
            or (docs / stem / "index.md").is_file()
            or (docs / stem / "README.md").is_file()
        )
        if not resolved:
            broken.append(url)
    assert not broken, (
        "README links to docs-site URLs with no source file under docs/ — these are "
        f"404s once Pages deploys: {sorted(set(broken))}"
    )


def test_every_in_page_anchor_matches_a_heading(readme):
    """[RL-3] ``[text](#anchor)`` must point at a heading that still exists.

    Renaming a heading silently breaks every anchor aimed at it; the link keeps
    rendering and simply goes nowhere.
    """
    anchors = _headings_as_anchors(readme)
    dangling = [
        t[1:] for t in _inline_targets(readme)
        if t.startswith("#") and t[1:] not in anchors
    ]
    assert not dangling, (
        f"README in-page anchors match no heading: {sorted(set(dangling))}. "
        f"Headings present: {sorted(anchors)}"
    )


def test_reference_style_links_are_defined_and_used(readme):
    """[RL-4] Both directions.

    An undefined reference renders as literal ``[text][name]`` on the page. A
    defined-but-unused one is dead weight that outlives whatever it pointed at —
    the badge whose workflow was deleted still has a definition here.
    """
    defined = set(_reference_definitions(readme))
    used = _reference_uses(readme)
    assert not (used - defined), f"used but never defined: {sorted(used - defined)}"
    assert not (defined - used), f"defined but never used: {sorted(defined - used)}"
