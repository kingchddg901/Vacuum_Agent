#!/usr/bin/env python3
"""Check that every generated doc in the tree matches what its generator emits now.

A generated document cannot drift from its source the way prose does — it drifts by
NOT BEING REGENERATED, which looks identical to being correct. `THEME_TOKEN_USAGE.md`
sat in the tree for four days across 31 commits to `src/styles/`; a fresh run moved
651 lines, and every `file:line` citation in it pointed at the wrong line. Nothing was
wrong with the generator. Nothing ran it.

That is the whole argument for this gate. The value of a generated layer is that it
states facts a human would get wrong — line-precise citations, exact counts — and that
value is entirely conditional on the file being current. An ungated generated doc is
strictly worse than prose: just as stale, and carrying a number, which reads as more
authoritative.

THIS ONE **IS** A CI GATE, unlike `check_docs_index.py`, and the distinction is not an
inconsistency. That script is a doc-commit rule because a new document legitimately
lands before the index pass that files it, so gating on it would fail pushes for work
that is not yet due (the 2026-06-12 `check_legend_drift.py` ruling). Staleness here is
the opposite shape: it is caused by a CODE change, the fix is one command with no
editorial judgement in it, and there is no later pass that is supposed to catch up.
Same reason `check-styles.mjs` gates the build.

What it checks:

  STALE     a tracked generated file whose generator now emits something else.
  MISSING   a registered file that is not in the tree at all.
  SILENT    a generator that ran clean and wrote nothing, or wrote the wrong names.
            A dead generator reads exactly like an up-to-date one, so this is a
            failure rather than a quiet pass.
  BROKEN    a generator that could not be run, timed out, or exited non-zero.
  UNGATED   a file carrying the GENERATED banner that no registry entry claims. The
            omission failure: adding a generator and forgetting to register it leaves
            it ungated, and nothing else would ever say so.

Line endings are normalised before comparison — generators emit LF, a Windows working
copy holds CRLF, and git normalises on commit, so a raw byte compare would fail on
Windows for a file that is perfectly current.

Run:
  python scripts/check_generated_docs.py          # check
  python scripts/check_generated_docs.py --fix    # regenerate in place, then check

Every detector here is ablated in `tests/unit/test_generated_doc_gate.py` (GDG-1..9):
a clean run against a clean tree proves nothing about a detector that is silently dead.

Exit code: 0 = every generated doc current, 1 = something is stale, missing or ungated.
"""
from __future__ import annotations

import argparse
import difflib
import os
import pathlib
import subprocess
import sys
import tempfile
from dataclasses import dataclass, field

ROOT = pathlib.Path(__file__).resolve().parent.parent

# The diffs this prints are doc content, full of em dashes and arrows. A Windows
# console defaults to cp1252, and a UnicodeEncodeError here would crash the gate on
# exactly the runs that have something to report.
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

# The marker docs carry on their first line. Kept for the docs-only helper
# `banner_bearing_files`; the repo-wide scan uses the richer patterns below.
BANNER_MARK = "GENERATED FILE"

# Directories scanned by the docs-only `banner_bearing_files` helper.
SCAN_DIRS = ("docs",)

# A RECOGNIZED banner: the header of a generated file, as a directive to whoever opens
# it. Matched only against the FIRST meaningful line (below), which is what separates a
# generated file (banner on line one) from a generator whose docstring merely mentions
# "the output is a GENERATED file" a few lines down. Any tracked file matching this MUST
# have a registry owner — that is the completeness gate.
import re  # noqa: E402  (local to the scan machinery)

RECOGNIZED_BANNER = re.compile(
    r"AUTO-?GENERATED|GENERATED FILE|GENERATED\s*[—–-]\s*DO NOT\s+(?:HAND-?EDIT|EDIT)",
    re.I,
)
# A SUSPECT header: looks generated but the banner is not on line one, or is phrased in
# a way RECOGNIZED does not know. Advisory only — it exists so a novel banner phrasing
# or a buried banner cannot silently escape the completeness demand; a human standardizes
# the banner to line one or registers the file.
SUSPECT_BANNER = re.compile(
    r"DO NOT\s+(?:HAND-?EDIT|EDIT BY HAND)|AUTO-?GENERATED|NEVER HAND-?EDIT|@generated",
    re.I,
)
# Non-text tracked files the banner scan skips (git tracks binaries too).
_BINARY_EXT = {
    ".png", ".jpg", ".jpeg", ".gif", ".webp", ".ico", ".bmp", ".woff", ".woff2",
    ".ttf", ".otf", ".eot", ".pdf", ".zip", ".gz", ".tgz", ".jar", ".map", ".svg",
    ".mp4", ".mov", ".webm", ".mp3", ".wav",
}


def _banner_line(text: str) -> str:
    """The first meaningful line: leading blanks and a shebang skipped.

    A generated file states its banner here; a generator's summary docstring states
    what it produces here, and only mentions 'GENERATED' further down. That difference
    is the whole reason the recognized scan looks at THIS line and no other.
    """
    lines = text.splitlines()
    i = 0
    while i < len(lines) and not lines[i].strip():
        i += 1
    if i < len(lines) and lines[i].lstrip().startswith("#!"):
        i += 1
        while i < len(lines) and not lines[i].strip():
            i += 1
    return lines[i] if i < len(lines) else ""


def _repo_text_files(root: pathlib.Path):
    """(relposix, path) for every text file to scan.

    Real repo: git's TRACKED set, so build artifacts, caches and scratchpad — none of
    which are maintained source — are excluded for free. A throwaway root that is not a
    git repo (the gate's own tests build these) falls back to a filesystem walk, so the
    completeness check still works there.
    """
    rels: list[str] = []
    try:
        proc = subprocess.run(
            ["git", "-C", str(root), "ls-files"],
            capture_output=True, text=True, timeout=60,
        )
        if proc.returncode == 0:
            rels = [ln for ln in proc.stdout.splitlines() if ln.strip()]
    except (OSError, subprocess.SubprocessError):
        rels = []
    if rels:
        pairs = ((rel, root / rel) for rel in rels)
    else:
        pairs = _walk_pruned(root)
    for rel, p in pairs:
        if p.suffix.lower() in _BINARY_EXT:
            continue
        yield rel, p


# Directories the git-less fallback walk never descends into: version control, package
# and build output, caches. Not maintained source, and crawling `.git`/`node_modules`
# on the real tree is what makes a git-less run appear to hang.
_WALK_PRUNE = {
    ".git", "node_modules", "dist", "build", ".venv", "venv", "__pycache__",
    ".mypy_cache", ".pytest_cache", ".ruff_cache", "coverage", "htmlcov", ".idea",
}


def _walk_pruned(root: pathlib.Path):
    for dirpath, dirnames, filenames in os.walk(root):
        dirnames[:] = [d for d in dirnames if d not in _WALK_PRUNE]
        for name in filenames:
            p = pathlib.Path(dirpath) / name
            yield p.relative_to(root).as_posix(), p


def _generator_scripts(generators: tuple[Generator, ...]) -> set[str]:
    """Repo-relative script paths that ARE generators — never generated outputs.

    Excluded from the SUSPECT scan so a generator whose docstring quotes the banner it
    writes (``gen_event_docs.py`` says 'the output is a GENERATED file') is not flagged.
    """
    return {
        part for gen in generators for part in gen.cmd
        if part.endswith((".py", ".mjs", ".js", ".sh"))
    }


def banner_scan(
    root: pathlib.Path = ROOT, generators: tuple[Generator, ...] | None = None
) -> tuple[set[str], set[str]]:
    """(recognized, suspect) repo-relative paths carrying a generated-file banner.

    RECOGNIZED — a known banner on the first meaningful line; CI demands a registry
    owner (the UNGATED failure). SUSPECT — a generated-looking header elsewhere or
    phrased differently; advisory, so the recognized set cannot silently rot.
    """
    if generators is None:  # resolved at call time — GENERATORS is defined below this
        generators = GENERATORS
    gen_scripts = _generator_scripts(generators)
    recognized: set[str] = set()
    suspect: set[str] = set()
    for rel, path in _repo_text_files(root):
        text = read(path)
        if text is None:
            continue
        if RECOGNIZED_BANNER.search(_banner_line(text)):
            recognized.add(rel)
            continue
        if rel in gen_scripts:
            continue
        head = "\n".join(text.splitlines()[:15])
        if SUSPECT_BANNER.search(head):
            suspect.add(rel)
    return recognized, suspect


def registered_files(
    generators: tuple[Generator, ...], root: pathlib.Path = ROOT
) -> set[str]:
    """Every output path the registry claims, with globs expanded against the tree."""
    reg: set[str] = set()
    for gen in generators:
        for pat in gen.files:
            if any(ch in pat for ch in "*?[]"):
                reg |= {p.relative_to(root).as_posix() for p in root.glob(pat)}
            else:
                reg.add(pat)
    return reg


@dataclass(frozen=True)
class Generator:
    """One generator and the tracked files it owns.

    Two shapes, because the repo has both:

    WHOLE-FILE (`out_env`) — the generator writes complete documents. Set the name
    of the environment variable it reads to redirect its output; this gate renders
    into a scratch directory and diffs. A generator wired in here MUST honour one: a
    check that writes over the tracked files and restores them afterwards leaves the
    tree dirty on exactly the run where it fails, which is the run you least want to
    be guessing about.

    REGION (`check_cmd`) — the generator rewrites a block inside a hand-written doc,
    so there is nothing to redirect. It brings its own staleness check instead, and a
    non-zero exit means stale. `files` is then documentation, not a comparison list.
    """

    id: str
    cmd: tuple[str, ...]  # regenerates in place; used by --fix (gated) / shown (map-only)
    files: tuple[str, ...]  # repo-relative posix paths; may contain globs
    out_env: str | None = None
    check_cmd: tuple[str, ...] | None = None
    note: str = ""
    env: dict[str, str] = field(default_factory=dict)
    # The authoritative inputs a human EDITS to change these outputs. Repo-relative
    # posix paths or dirs; MAY point OUTSIDE the tree (e.g. durable/ TM fixtures) —
    # those are provenance edges the map shows but the gate never tries to run from.
    sources: tuple[str, ...] = ()
    # GATED (default): CI runs the generator and diffs, so it must be re-runnable from
    # in-tree inputs. MAP-ONLY (gated=False): its inputs live outside the tree or it is
    # only run by hand, so the gate does NOT run it — but the generation map still shows
    # it and UNGATED still demands it own its banner-bearing outputs. Distinct because
    # trying to run a durable-fed generator in CI is BROKEN, not a staleness verdict.
    gated: bool = True
    # Exact command(s) a human runs, when it is not a single tuple `cmd` (a two-step
    # pipeline, a per-file codegen). Falls back to `hint` (derived from cmd) when empty.
    regen: str = ""

    def __post_init__(self) -> None:
        if self.gated:
            if bool(self.out_env) == bool(self.check_cmd):
                raise ValueError(
                    f"gated generator {self.id!r} must set exactly one of out_env"
                    " (whole-file, render-and-diff) or check_cmd (region, own check)"
                )
        elif self.out_env or self.check_cmd:
            raise ValueError(
                f"map-only generator {self.id!r} sets out_env/check_cmd — those wire the"
                " staleness runner it is opted OUT of; drop them or set gated=True"
            )

    @property
    def regen_cmd(self) -> str:
        """The regenerate command shown in the map — explicit `regen` or the `hint`."""
        return self.regen or self.hint

    @property
    def hint(self) -> str:
        """The regenerate command as a human would type it.

        `cmd` carries `sys.executable` so the subprocess runs under the same
        interpreter as the gate; printing that verbatim gives the reader an absolute
        machine-specific path to copy. Show `python`.
        """
        head, *rest = self.cmd
        return " ".join(["python" if head == sys.executable else head, *rest])

    @property
    def out_dir(self) -> str:
        """The directory a whole-file generator writes into, from its own files."""
        parents = {str(pathlib.PurePosixPath(f).parent) for f in self.files}
        if len(parents) != 1:
            raise ValueError(
                f"generator {self.id!r} names files in {len(parents)} directories"
                f" ({sorted(parents)}); one generator writes into one output dir"
            )
        return parents.pop()


GENERATORS: tuple[Generator, ...] = (
    Generator(
        id="theme-tokens",
        cmd=("node", "scripts/gen-theme-token-docs.mjs"),
        out_env="EVCC_GENDOC_OUT",
        files=(
            "docs/dev/reference/THEME_TOKEN_MAP.md",
            "docs/dev/reference/THEME_TOKEN_USAGE.md",
        ),
        sources=("src/theme-tokens/", "src/styles/"),
        note="theme editor registry + card CSS",
    ),
    # MOVED OUT OF `.claude/` 2026-09-13. Generator and output both lived under the
    # ignored tree, so two tests in tests/unit/test_adapter_config_parity.py read a file
    # that CANNOT exist in CI — they failed there from the day they were written and
    # nobody saw it, because Tests had not run on master since 2026-08-26. Being here
    # also makes it GATED for the first time: it was the one generated doc nothing
    # checked for staleness.
    Generator(
        id="adapter-config",
        cmd=(sys.executable, "scripts/gen_adapter_config_docs.py"),
        out_env="EVCC_GENDOC_OUT",
        files=(
            "docs/dev/reference/ADAPTER-CONFIG.generated.md",
            "docs/dev/reference/CAPABILITY-FLAGS.generated.md",
        ),
        sources=(
            "custom_components/eufy_vacuum/adapters/config_schema.py",
            "custom_components/eufy_vacuum/adapters/registry.py",
            "custom_components/eufy_vacuum/core/capabilities.py",
            "custom_components/eufy_vacuum/adapters/eufy/adapter.py",
            "custom_components/eufy_vacuum/adapters/roborock/adapter.py",
            "custom_components/eufy_vacuum/adapters/dreame/adapter.py",
            # The generator also runs a conservative static scan for READ SITES of each
            # config key and prints them WITH LINE NUMBERS, so these three feed the output
            # too. They were missing from this list when the generator was registered,
            # which left GENERATION_MAP telling a reader to edit six files when nine can
            # move the doc. The gate itself was unaffected -- it regenerates and diffs, so
            # it caught the drift anyway; it is the "EDIT HERE" map that was wrong.
            #
            # ⚠ Because those citations carry line numbers, ANY insertion in these files
            # restales this doc, even one that changes nothing it documents. Adding a
            # snapshot field to core/manager.py shifted a cited read site from :6369 to
            # :6387 and that alone turned the gate red.
            "custom_components/eufy_vacuum/core/manager.py",
            "custom_components/eufy_vacuum/diagnostics.py",
            "custom_components/eufy_vacuum/mapping/mapping_services.py",
        ),
        note="the adapter config contract, witnessed by all three shipped adapters",
    ),
    Generator(
        id="events",
        cmd=(sys.executable, "scripts/gen_event_docs.py"),
        out_env="EVCC_GENDOC_OUT",
        files=("docs/dev/reference/EVENTS.md",),
        sources=("custom_components/eufy_vacuum/",),
        note="every hass.bus.async_fire call site",
    ),
    # The Mocking column in every subsystem coverage table. A region generator: it
    # rewrites cells inside hand-written pages, so there is no whole file to diff.
    # It shipped with a --check mode and a docstring calling it "CI: fail if stale",
    # and nothing ever ran it — two pages were stale when this gate was written.
    Generator(
        id="mock-column",
        cmd=(sys.executable, "scripts/mock_docs.py"),
        check_cmd=(sys.executable, "scripts/mock_docs.py", "--check"),
        files=("docs/testing/subsystems/*.md",),
        sources=("tests/",),
        note="the generated Mocking column, from the mock census",
    ),
    # ── MAP-ONLY entries ─────────────────────────────────────────────────────────
    # Re-runnable only from inputs OUTSIDE the tree (durable/ TM fixtures) or by hand,
    # so the gate does not run them — but the generation map shows them and UNGATED
    # still demands they own their banner-bearing outputs.
    # ⛔ `eufy-guides` / `roborock-guides` REMOVED 2026-09-11. They registered
    # scripts/build_guides.py + emit_libs.py, the LIFT pipeline that rewrote both brands'
    # guide libraries with the vendors' own manual wording. That content was reverted to its
    # pre-lift state (the libraries are hand-authored again), so there is no generator to
    # gate and a registered generator whose output is no longer generated reads as drift.
    # The replacement is the KEY system (adapters/dreame/upkeep_keys.py), which authors
    # sentences rather than merging lifted cells — nothing in emit_libs.py's shape carries
    # over. Chris's call: "emit_libs.py can be removed from check_generated_docs.py unless
    # we are going to use its shape."
    Generator(
        id="dreame-guide-keys",
        cmd=(sys.executable, "scripts/sync-dreame-guide-keys.py"),
        # NOT gated: the SOURCE is the authoring fixture, which lives OUTSIDE git
        # (durable/dreame-port-fixture/). CI cannot re-run this, so a drift check here would
        # fail on every machine that is not Chris's. The gate that matters instead is inside
        # the script — it REFUSES to write unless every key the backend can emit is present in
        # all 18 packs — plus [DUK-7], which asserts the shipped English pack covers the
        # emitted key set from inside the test suite.
        gated=False,
        files=(
            "src/i18n/guide-keys.js",
            "custom_components/eufy_vacuum/frontend/guides/keys/*.json",
        ),
        sources=("durable/dreame-port-fixture/resources/key-authoring/",),
        regen="python scripts/sync-dreame-guide-keys.py",
        note="the 18 Dreame key packs -> bundled EN + served per-lang key JSON",
    ),
    # REMOVED 2026-09-12 — the "guide-translations" generator. All three brands ship i18n
    # KEYS now, so the family-prose channel has no producer and no source: eufy's packs went
    # with its port, roborock's with this one, and scripts/sync-guide-translations.py was the
    # last consumer of either. `src/i18n/guide-translations.js` is still on disk and is inert
    # (the card returns on the key-routed branch before it is ever consulted); it and the
    # card's family branch come out in their own commit, where a frontend change can be
    # reviewed as one. Listing a generator whose script does not exist would fail this gate
    # for a reason that has nothing to do with drift.
    Generator(
        id="locale-reference",
        cmd=("node", "scripts/build-locale-reference.mjs"),
        gated=False,
        files=("custom_components/eufy_vacuum/frontend/locales/en.reference.jsonc",),
        sources=("src/i18n/en.js",),
        regen="npm run build:locale-reference",
        note="translator reference: full nested key structure + context comments of en.js",
    ),
    Generator(
        id="animal-modules",
        cmd=("node", "scripts/build-animal.mjs"),
        gated=False,
        files=("custom_components/eufy_vacuum/frontend/animal-svg/animals/*.js",),
        sources=("custom_components/eufy_vacuum/frontend/animal-svg/src/",),
        regen="node scripts/build-animal.mjs <descriptor.json> --first-party",
        note="per-animal codegen from a sanitised descriptor; own gate is check-animal-pr",
    ),
    # ── the map itself — gated, so it can never go stale about the others ─────────
    Generator(
        id="generation-map",
        cmd=(sys.executable, "scripts/gen_generation_map.py"),
        out_env="EVCC_GENDOC_OUT",
        files=("docs/dev/reference/GENERATION_MAP.md",),
        sources=("scripts/check_generated_docs.py",),
        note="this registry, rendered as the who-generates-what navigation graph",
    ),
)


def norm(text: str) -> str:
    """Content with line endings normalised, so CRLF working copies compare equal.

    Belt to `read_text`'s braces, and named as such after a mutation probe: blinding
    this function changes nothing today, because `Path.read_text` already applies
    universal-newline translation. It is kept for the read path that would not —
    anyone switching to `read_bytes().decode()` for a BOM or encoding reason gets a
    gate that still works instead of one that reports every Windows file stale.
    """
    return text.replace("\r\n", "\n").replace("\r", "\n")


def read(path: pathlib.Path) -> str | None:
    try:
        return norm(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeDecodeError):
        return None


def run(
    cmd: tuple[str, ...],
    gen: Generator,
    *,
    out_dir: pathlib.Path | None = None,
    root: pathlib.Path = ROOT,
) -> tuple[int | None, str]:
    """Run a command for `gen`, optionally redirecting output.

    Returns (returncode, message). A returncode of None means the command could not
    be run at all — that is BROKEN, not a verdict. Keeping it distinct matters for
    region generators, where a non-zero exit is the finding: `node` missing from the
    runner must not be reported as "your docs are stale".
    """
    env = dict(os.environ)
    if gen.out_env:
        if out_dir is not None:
            env[gen.out_env] = str(out_dir)
        else:
            # --fix writes in place. Drop any inherited redirect, or a stale value
            # in the caller's shell silently sends the regenerated docs elsewhere
            # and the tree is "fixed" without changing.
            env.pop(gen.out_env, None)
    env.update(gen.env)
    try:
        proc = subprocess.run(
            list(cmd),
            cwd=root,
            env=env,
            capture_output=True,
            text=True,
            timeout=600,
        )
    except (FileNotFoundError, NotADirectoryError, PermissionError) as exc:
        return None, f"could not run {cmd[0]!r}: {exc}"
    except subprocess.TimeoutExpired:
        return None, "timed out after 600s"
    if proc.returncode != 0:
        tail = (proc.stderr or proc.stdout or "").strip().splitlines()[-8:]
        return proc.returncode, "exited %d\n%s" % (
            proc.returncode,
            "\n".join("      " + ln for ln in tail),
        )
    return 0, ""


def banner_bearing_files(
    root: pathlib.Path = ROOT, scan_dirs: tuple[str, ...] = SCAN_DIRS
) -> set[str]:
    """Every doc under `scan_dirs` whose first non-empty line carries the banner."""
    found: set[str] = set()
    for d in scan_dirs:
        base = root / d
        if not base.is_dir():
            continue
        for path in sorted(base.rglob("*.md")):
            text = read(path)
            if text is None:
                continue
            # First non-empty line only: a doc that *describes* the banner in its
            # body (the design notes do) must not be swept up as a generated file.
            first = next((ln for ln in text.splitlines() if ln.strip()), "")
            if BANNER_MARK in first:
                found.add(path.relative_to(root).as_posix())
    return found


def check(
    generators: tuple[Generator, ...],
    *,
    root: pathlib.Path = ROOT,
    scan_dirs: tuple[str, ...] = SCAN_DIRS,
    diff_lines: int = 25,
) -> tuple[list[str], list[str], list[str]]:
    """Returns (problems, files compared, generator ids that ran)."""
    problems: list[str] = []
    checked: list[str] = []
    ran: list[str] = []

    if not generators:
        return ["FAIL     the generator registry is empty — this gate checks nothing"], [], []

    with tempfile.TemporaryDirectory(prefix="evcc-gendoc-") as tmp:
        for gen in generators:
            # MAP-ONLY — its inputs are outside the tree (durable/ fixtures) or it is
            # run by hand, so the gate does not run it. It still owns its outputs for
            # the UNGATED completeness scan below; it just is not staleness-diffed.
            if not gen.gated:
                continue
            # REGION generator — it brings its own check; non-zero means stale.
            if gen.check_cmd:
                rc, msg = run(gen.check_cmd, gen, root=root)
                if rc is None:
                    problems.append(f"BROKEN   {gen.id}: {msg}")
                    continue
                ran.append(gen.id)
                checked.extend(gen.files)
                if rc != 0:
                    problems.append(
                        f"STALE    {gen.id} ({', '.join(gen.files)})\n"
                        f"      regenerate:  {gen.hint}\n      {msg}"
                    )
                continue

            out_dir = pathlib.Path(tmp) / gen.id
            out_dir.mkdir(parents=True, exist_ok=True)

            rc, msg = run(gen.cmd, gen, out_dir=out_dir, root=root)
            if rc != 0:
                problems.append(f"BROKEN   {gen.id}: {msg}")
                continue
            ran.append(gen.id)

            wrote = sorted(p.name for p in out_dir.rglob("*") if p.is_file())
            if not wrote:
                # A generator that exits 0 and writes nothing passes a naive
                # comparison loop by iterating zero times. Name it.
                problems.append(
                    f"SILENT   {gen.id}: exited 0 and wrote no files into"
                    f" ${gen.out_env} — either the override is not honoured or the"
                    " generator is dead"
                )
                continue

            for rel in gen.files:
                fresh = read(out_dir / pathlib.PurePosixPath(rel).name)
                if fresh is None:
                    problems.append(
                        f"SILENT   {rel}: {gen.id} is registered as its owner but"
                        f" wrote {wrote} instead"
                    )
                    continue

                current = read(root / rel)
                if current is None:
                    problems.append(f"MISSING  {rel}: registered, not in the tree")
                    continue

                checked.append(rel)
                if current == fresh:
                    continue

                diff = list(
                    difflib.unified_diff(
                        current.splitlines(),
                        fresh.splitlines(),
                        fromfile=f"{rel} (in tree)",
                        tofile=f"{rel} (generator, now)",
                        lineterm="",
                        n=0,
                    )
                )
                body = "\n".join("      " + ln for ln in diff[:diff_lines])
                more = len(diff) - diff_lines
                if more > 0:
                    body += f"\n      … {more} more diff lines"
                problems.append(
                    f"STALE    {rel}\n      regenerate:  {gen.hint}\n{body}"
                )

    # UNGATED — a generated file nobody registered. The omission failure, now REPO-WIDE
    # and banner-driven (not docs-only): every TRACKED file whose first meaningful line
    # is a recognized GENERATED banner must have an owner, wherever it lives.
    registered = registered_files(generators, root)
    recognized, _suspect = banner_scan(root, generators)
    for rel in sorted(recognized - registered):
        problems.append(
            f"UNGATED  {rel}: carries a GENERATED banner but no entry in GENERATORS"
            " owns it, so nothing records how to regenerate it or what it is generated"
            " from"
        )

    return problems, checked, ran


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument(
        "--fix",
        action="store_true",
        help="regenerate every registered doc in place, then re-check",
    )
    ap.add_argument(
        "--diff-lines",
        type=int,
        default=25,
        help="how many diff lines to print per stale file (default 25)",
    )
    args = ap.parse_args()

    if args.fix:
        for gen in GENERATORS:
            if not gen.gated:
                # Map-only: durable/ inputs or a per-file/by-hand run. --fix can neither
                # provide those nor guess the arguments, so it does not touch them.
                print(f"skipped      {gen.id} (map-only; regen: {gen.regen_cmd})")
                continue
            # Both shapes regenerate the same way — in place, with gen.cmd. The
            # out_env redirect exists only so the CHECK can avoid touching the tree.
            rc, msg = run(gen.cmd, gen)
            ok = rc == 0
            print(("regenerated  " if ok else "FAILED       ") + gen.id
                  + (f"\n      {msg}" if msg else ""))
            if not ok:
                return 1

    problems, checked, ran = check(GENERATORS, diff_lines=args.diff_lines)

    for p in problems:
        print(p)

    if not checked and not problems:
        # Belt and braces: reaching here with nothing compared means the registry
        # resolved to no readable output. Do not print a clean result for that.
        print("FAIL     compared zero files — the registry names no readable output")
        return 1

    # SUSPECT — advisory, not a failure: a header that looks generated but whose banner
    # is not on line one or is phrased in a way RECOGNIZED does not know. Surfaced so the
    # recognized set cannot silently rot; a human standardizes the banner or registers it.
    _recognized, suspect = banner_scan()
    for rel in sorted(suspect - registered_files(GENERATORS)):
        print(f"SUSPECT  {rel}: header looks generated but its banner is not recognized"
              " on line one — standardize the banner, or register + own it")

    gated = sum(1 for g in GENERATORS if g.gated)
    maponly = len(GENERATORS) - gated
    print()
    print(
        f"{len(ran)}/{gated} gated generators ran · {maponly} map-only ·"
        f" {len(checked)} files compared · {len(problems)} problem(s)"
    )
    if problems:
        print("Fix with:  python scripts/check_generated_docs.py --fix")
    return 1 if problems else 0


if __name__ == "__main__":
    sys.exit(main())
