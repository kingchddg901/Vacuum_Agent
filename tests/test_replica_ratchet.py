"""The register ratchet — a registry and its anchors must not drift apart.

WHY THIS EXISTS, and it is not hypothetical. On 2026-08-18 seven `RN` anchors were
declared in source, marked at both members, and present in NO DOCUMENT AT ALL —
while `doc_anchor.py --check` reported 0 problems and `--orphans` reported 0
orphans. Both gates were clean and the register was missing a third of its sets.

`--orphans` asks "does any document cite this anchor?" and a `REPLICA` marker in
SOURCE satisfies it, because the citation scan reads reference files, not just
docs. So a set can be fully wired in code and invisible in `00c`, forever, with
every shipped gate green. That is the specific hole this closes.

WHAT IT CHECKS -- both directions, because they fail differently:

  declared -> registered   an anchor in source with no `### `TOKEN`` entry. The
                           rule exists in the code and nowhere a reader looks.
  registered -> declared   an entry with no anchor site. A rule with no home:
                           00b's own standard is that an entry names its
                           enforcement site, so this is that standard, enforced.
  RN well-formedness       exactly ONE `anchor:` primary and AT LEAST ONE
                           `REPLICA` per set. Three placements during the census
                           briefly left a primary with no replica -- a half-wired
                           set that no existing gate can see.

WHY IT IMPORTS doc_anchor INSTEAD OF RE-SCANNING. A second parser is a second
answer to "what counts as declared", and it WILL diverge. Writing this, a
hand-rolled regex requiring a `#`/`//`/`*` comment prefix reported INMKEHPQ and
INSJM6KC as unregistered; both are fine, and INSJM6KC is declared inside a
docstring. A ratchet that cries wolf gets deleted, so the tool owns the question
and this file owns only the comparison.

CN IS DELIBERATELY EXEMPT. `00b` indexes IN and `00c` indexes RN; CN (code
notation) has no registry by design, so requiring one would invent a rule.
"""

from __future__ import annotations

import re
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

import doc_anchor  # noqa: E402  (path set above)

REGISTRIES = {
    "IN": ROOT / "docs" / "dev" / "00b-invariants.md",
    "RN": ROOT / "docs" / "dev" / "00c-replicas.md",
}
ENTRY_RE = re.compile(r"^###\s*`([A-Z]{2}[0-9A-Z]{6})`", re.M)
REPLICA_RE = re.compile(r"REPLICA\s+(RN[0-9ABCDEFGHJKMNPQRSTVWXYZ]{6})\b")


def _declared() -> dict[str, list]:
    """Every anchor declared in source, per doc_anchor's OWN parser."""
    return doc_anchor.scan()


def _registered(prefix: str) -> set[str]:
    doc = REGISTRIES[prefix]
    return {t for t in ENTRY_RE.findall(doc.read_text(encoding="utf-8")) if t.startswith(prefix)}


@pytest.mark.parametrize("prefix", sorted(REGISTRIES))
def test_declared_anchors_are_registered(prefix):
    """[RR-1] An anchor declared in source has an entry in its registry."""
    declared = {t for t in _declared() if t.startswith(prefix)}
    missing = sorted(declared - _registered(prefix))
    assert not missing, (
        f"{prefix} anchors declared in source with no `### `TOKEN`` entry in "
        f"{REGISTRIES[prefix].relative_to(ROOT)}: {missing}\n"
        "The rule exists in the code and nowhere a reader looks. Note that "
        "doc_anchor --orphans will NOT catch this: a REPLICA marker in source "
        "counts as a citation."
    )


@pytest.mark.parametrize("prefix", sorted(REGISTRIES))
def test_registered_anchors_are_declared(prefix):
    """[RR-2] A registry entry names a real anchor site."""
    declared = {t for t in _declared() if t.startswith(prefix)}
    orphaned = sorted(_registered(prefix) - declared)
    assert not orphaned, (
        f"{prefix} registry entries with no `anchor:` site in source: {orphaned}\n"
        "00b's own standard is that an entry names its enforcement site."
    )


def test_replica_sets_are_well_formed():
    """[RR-3] Each RN set has exactly one primary and at least one replica.

    A primary with no replica is a set of one, which is not a set. A set with two
    primaries has no source of truth. Neither is visible to --check or --orphans.
    """
    primaries = {t: len(v) for t, v in _declared().items() if t.startswith("RN")}
    replicas: dict[str, int] = {}
    for path in doc_anchor.source_files():
        try:
            text = path.read_text(encoding="utf-8", errors="replace")
        except OSError:  # unreadable artefact dirs on Windows
            continue
        for token in REPLICA_RE.findall(text):
            replicas[token] = replicas.get(token, 0) + 1

    bad = []
    for token, n_primary in sorted(primaries.items()):
        n_replica = replicas.get(token, 0)
        if n_primary != 1 or n_replica < 1:
            bad.append(f"{token}: {n_primary} primary, {n_replica} replica")
    stray = sorted(set(replicas) - set(primaries))
    assert not bad and not stray, (
        f"malformed replica sets: {bad or 'none'}\n"
        f"REPLICA markers with no primary: {stray or 'none'}"
    )
