#!/usr/bin/env python3
"""Render `docs/dev/reference/GENERATION_MAP.md` from the generator registry.

A checked-in file that says "GENERATED / DO NOT EDIT" answers three questions badly: an
agent that lands on it has to WALK the provenance — read its banner, find the generator,
read THAT for its inputs, and so on up a chain that sometimes forks. This map turns the
walk into one lookup: for every generated artifact, who owns it, what it is generated
FROM, what regenerates it, and what downstream artifacts change when it does.

SINGLE SOURCE OF TRUTH. Every fact here is read from the `GENERATORS` registry in
`scripts/check_generated_docs.py` — the same registry whose UNGATED scan fails CI when a
banner-bearing tracked file has no owner. So this map cannot omit a generated file
without CI going red first, and it cannot drift from the registry because it IS the
registry, rendered. It does not re-parse banners or guess.

Determinism: globs are expanded against git's TRACKED set, not the filesystem, so an
on-disk-but-uncommitted artifact (e.g. a pending i18n bundle) does not make the map
differ between a working tree and a clean CI checkout.

Output: honours $EVCC_GENDOC_OUT (the gate renders into a scratch dir and diffs); writes
in place otherwise. Regenerate:  python scripts/gen_generation_map.py
"""
from __future__ import annotations

import fnmatch
import os
import pathlib
import subprocess
import sys

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
from check_generated_docs import (  # noqa: E402  single source of truth
    GENERATORS,
    Generator,
    banner_scan,
)

ROOT = pathlib.Path(__file__).resolve().parent.parent
REL_OUT = "docs/dev/reference/GENERATION_MAP.md"
BANNER = (
    "<!-- GENERATED FILE — DO NOT EDIT BY HAND. "
    "Regenerate: python scripts/gen_generation_map.py -->"
)


def tracked_files() -> list[str]:
    proc = subprocess.run(
        ["git", "-C", str(ROOT), "ls-files"], capture_output=True, text=True, timeout=60
    )
    return sorted(ln for ln in proc.stdout.splitlines() if ln.strip())


def is_glob(pat: str) -> bool:
    return any(ch in pat for ch in "*?[]")


def expand(pat: str, tracked: list[str]) -> list[str]:
    """Committed files a `files` pattern names — globs matched against the tracked set."""
    if is_glob(pat):
        return sorted(f for f in tracked if fnmatch.fnmatch(f, pat))
    return [pat] if pat in tracked else [pat]  # a plain path is shown even if new


def feeds(source: str, output: str) -> bool:
    """True if a consumer's `source` SPECIFICALLY depends on `output`.

    Strict on purpose: a whole-package scan source (``custom_components/eufy_vacuum/``,
    read for every ``async_fire`` site) must NOT read as depending on every generated
    file that happens to live under it. So a directory source matches only files sitting
    DIRECTLY in it, not arbitrarily deep — that is the difference between "this dir of
    inputs" (the i18n packs) and "this subtree I analyse" (the package).
    """
    if is_glob(source):
        return fnmatch.fnmatch(output, source)
    src = source.rstrip("/")
    return output == src or str(pathlib.PurePosixPath(output).parent) == src


def is_external(source: str) -> bool:
    """A provenance-only source outside the maintained tree (durable fixtures, etc.)."""
    return source.startswith("durable/") or not (ROOT / source.rstrip("/")).exists()


def outputs_of(gen: Generator, tracked: list[str], recognized: set[str]) -> list[str]:
    """The generated files this generator owns.

    A WHOLE-FILE glob is kept only where the match carries a generated banner, so a
    hand-written sibling swept in by ``*.py`` (e.g. an ``__init__.py`` package loader
    ``emit_libs`` never writes) is not mislabelled DO-NOT-EDIT. A REGION generator's
    files are hand-written pages with a generated block inside — none carry a line-one
    banner, so its glob is shown as-is. Explicit paths are trusted as declared
    (guide-translations.js buries its banner yet is a real whole-file output).
    """
    region = gen.check_cmd is not None
    out: list[str] = []
    for pat in gen.files:
        if is_glob(pat) and not region:
            out.extend(f for f in expand(pat, tracked) if f in recognized)
        else:
            out.extend(expand(pat, tracked))
    return sorted(dict.fromkeys(out))


def summarize_files(files: list[str]) -> str:
    """Name a few files; collapse a run of same-dir siblings into `dir/*.ext (N)`.

    A singleton is always named, even inside the collapse, so a lone lib beside a big
    i18n directory reads as its filename, not `dir/*.py (1)`.
    """
    if len(files) <= 3:
        return ", ".join(f"`{f}`" for f in files)
    by_dir: dict[str, list[str]] = {}
    for f in files:
        by_dir.setdefault(str(pathlib.PurePosixPath(f).parent), []).append(f)
    parts: list[str] = []
    for d, fs in sorted(by_dir.items()):
        if len(fs) == 1:
            parts.append(f"`{fs[0]}`")
            continue
        by_ext: dict[str, int] = {}
        for f in fs:
            ext = pathlib.PurePosixPath(f).suffix
            by_ext[ext] = by_ext.get(ext, 0) + 1
        parts.extend(f"`{d}/*{ext}` ({n})" for ext, n in sorted(by_ext.items()))
    return " · ".join(parts)


def source_cell(gen: Generator) -> str:
    if not gen.sources:
        return "—"
    bits = []
    for s in gen.sources:
        bits.append(f"`{s}`" + (" _(external)_" if is_external(s) else ""))
    return " · ".join(bits)


def main() -> int:
    tracked = tracked_files()
    recognized, _suspect = banner_scan()
    gens = sorted(GENERATORS, key=lambda g: g.id)
    outs = {g.id: outputs_of(g, tracked, recognized) for g in gens}

    # downstream: generators whose SOURCES specifically depend on one of this
    # generator's outputs (a chain edge — the i18n packs feeding guide-translations).
    downstream: dict[str, list[str]] = {}
    for g in gens:
        deps = set()
        for other in gens:
            if other.id == g.id:
                continue
            if any(feeds(s, o) for s in other.sources for o in outs[g.id]):
                deps.add(other.id)
        downstream[g.id] = sorted(deps)

    L: list[str] = [BANNER, "", "# Generation map", ""]
    L += [
        "One authoritative graph of every checked-in **generated** artifact: who owns it,",
        "what it is generated **from**, what **regenerates** it, and what changes",
        "**downstream** when its source does. Rendered from the `GENERATORS` registry in",
        "[`scripts/check_generated_docs.py`](../../../scripts/check_generated_docs.py); that",
        "gate's UNGATED scan fails CI if any banner-bearing tracked file is missing here, so",
        "this map is complete by construction. **Do not hand-edit** — edit the registry.",
        "",
        "- **gated** — CI runs the generator and fails if the tree is stale (inputs are in-tree).",
        "- **map-only** — inputs live outside the tree (e.g. `durable/` fixtures) or it is run",
        "  by hand, so CI does not staleness-check it; it is still owned and mapped.",
        "",
        "## The graph",
        "",
        "| output(s) | gate | generated&nbsp;by | edit instead (sources) | downstream |",
        "|---|---|---|---|---|",
    ]
    for g in gens:
        gate = "map-only" if not g.gated else ("gated · region" if g.check_cmd else "gated")
        dn = ", ".join(f"`{d}`" for d in downstream[g.id]) or "—"
        L.append(
            f"| {summarize_files(outs[g.id])} | {gate} | `{g.id}` "
            f"({g.regen_cmd}) | {source_cell(g)} | {dn} |"
        )

    # Reverse index — "I need to change X": every distinct source -> what regenerates.
    L += ["", "## Reverse index — “I need to change …”", ""]
    src_to_gens: dict[str, list[Generator]] = {}
    for g in gens:
        for s in g.sources:
            src_to_gens.setdefault(s, []).append(g)
    for s in sorted(src_to_gens):
        tag = " _(external, provenance only)_" if is_external(s) else ""
        for g in src_to_gens[s]:
            regen_note = f" — **but `{s}` is itself generated; edit ITS source above**" if (
                any(feeds(s, o) for other in gens for o in outs[other.id])
            ) else ""
            L.append(
                f"- **`{s}`**{tag} → regenerates {summarize_files(outs[g.id])} · "
                f"run `{g.regen_cmd}`{regen_note}"
            )

    # Per-generator EDIT / DO NOT EDIT / REGEN — the thing you actually want at edit time.
    L += ["", "## Per generator — edit here, never there", ""]
    for g in gens:
        L += [f"### `{g.id}`{'' if g.gated else '  ·  map-only'}"]
        if g.note:
            L.append(f"_{g.note}_")
        edit = ", ".join(f"`{s}`" + (" (external)" if is_external(s) else "")
                         for s in g.sources) or "—"
        L += [
            f"- **EDIT HERE:** {edit}",
            f"- **DO NOT EDIT:** {summarize_files(outs[g.id])}",
            f"- **REGEN:** `{g.regen_cmd}`",
            "",
        ]

    text = "\n".join(L).rstrip() + "\n"
    out_dir = os.environ.get("EVCC_GENDOC_OUT")
    dest = (pathlib.Path(out_dir) / "GENERATION_MAP.md") if out_dir else (ROOT / REL_OUT)
    dest.parent.mkdir(parents=True, exist_ok=True)
    dest.write_text(text, encoding="utf-8")
    print(f"wrote {dest} — {len(gens)} generators, {sum(len(v) for v in outs.values())} outputs")
    return 0


if __name__ == "__main__":
    sys.exit(main())
