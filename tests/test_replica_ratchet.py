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

PN INVERTS THE QUESTION, so it gets its own check rather than the shared pair.
A PN anchors a rule with NO code site -- "never edit .storage", "a service call
moves hardware" -- so "is it declared at a site?" is meaningless: it is declared
in `00b`, because the reasoning IS the artifact. The meaningful question is the
reverse. A PN that nothing cites is a document with a token on it, so [RR-4]
asks whether anything actually points at it.
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
# PN lives in 00b too, but is checked by RR-4 rather than the shared pair above.
PN_REGISTRY = ROOT / "docs" / "dev" / "00b-invariants.md"
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


# Dated records are not evidence of liveness. `docs/dev/history/` and
# `maintenance/` are as-of-their-date accounts, and the repo's own citation and
# index gates already exclude them for exactly this reason. A PN kept alive by a
# mention in a historical note is the prose equivalent of a test that bites the
# wrong thing -- technically green, attached to nothing current.
HISTORICAL = ("docs/dev/history/", "docs/dev/maintenance/", "docs/dev/deltas/",
              ".claude/")


def test_prose_anchors_have_a_live_consumer():
    """[RR-4] A PROSE-DECLARED anchor is cited by at least one LIVE artifact.
    The inverse of [RR-1]/[RR-2].

    Covers every class that declares in prose, asked of doc_anchor itself rather than
    hardcoded -- EN (a rule binding a person, no code site) and PN (a pointer to where
    the canonical explanation lives). Both are declared in a document because the
    document IS the artifact, so "is it declared at a site?" cannot be the check.

    ⚠ THIS TEST WAS HARDCODED TO "PN" AND CAUGHT THE 2026-08-22 RECLASSIFICATION BY
    GOING RED -- the three rules moved to EN, PN went to zero members, and the canary
    below fired. Sweeping the three TOKENS did not touch a guard keyed on the CLASS.
    Retiring a class means sweeping its name, not only its instances. What makes it earn
    its place is being pointed at from something that still runs or is still read:
    the code the rule constrains, a procedure, a test.

    NECESSARY, NOT SUFFICIENT, and deliberately so. This proves REACHABILITY, not
    that the citation is apt. A decorative citation passes here and is caught by
    review, the same division as every other ratchet in this repo: the machine shows
    the relationship is structurally present, a human decides it is the right one.
    """
    declared = sorted(
        t for t in _declared() if t.startswith(doc_anchor.PROSE_DECL_PREFIXES)
    )
    assert declared, (
        "no prose-declared anchors found for any of "
        f"{doc_anchor.PROSE_DECL_PREFIXES} — the prose-declaration path is broken"
    )

    live: dict[str, list[str]] = {t: [] for t in declared}
    for path in doc_anchor.ref_files():
        rel = path.relative_to(ROOT).as_posix()
        if rel == "docs/dev/00b-invariants.md":
            continue  # the declaration is not a citation of itself
        if any(rel.startswith(h) for h in HISTORICAL):
            continue
        try:
            text = path.read_text(encoding="utf-8", errors="replace")
        except OSError:
            continue
        for token in declared:
            if token in text:
                live[token].append(rel)

    uncited = sorted(t for t, where in live.items() if not where)
    assert not uncited, (
        f"prose-declared anchors with no LIVE consumer: {uncited}. "
        "A rule with no code site earns its place by being pointed at from "
        "something current — the code it constrains, a procedure, a test. A "
        "mention in history/ or maintenance/ does not count: those are dated "
        "records, and a rule kept alive by one is attached to nothing."
    )
