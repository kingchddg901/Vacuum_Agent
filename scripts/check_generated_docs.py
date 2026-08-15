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

# The marker every generated doc carries on its first line. Used two ways: the
# generators write it, and the UNGATED scan looks for tracked files carrying it that
# no registry entry owns.
BANNER_MARK = "GENERATED FILE"

# Directories scanned for the UNGATED check. Anything outside these may carry the
# words "GENERATED FILE" in ordinary prose without tripping the gate.
SCAN_DIRS = ("docs",)


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
    cmd: tuple[str, ...]  # regenerates in place; used by --fix
    files: tuple[str, ...]  # repo-relative posix paths
    out_env: str | None = None
    check_cmd: tuple[str, ...] | None = None
    note: str = ""
    env: dict[str, str] = field(default_factory=dict)

    def __post_init__(self) -> None:
        if bool(self.out_env) == bool(self.check_cmd):
            raise ValueError(
                f"generator {self.id!r} must set exactly one of out_env (whole-file,"
                " render-and-diff) or check_cmd (region, brings its own check)"
            )

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
        note="theme editor registry + card CSS",
    ),
    Generator(
        id="events",
        cmd=(sys.executable, "scripts/gen_event_docs.py"),
        out_env="EVCC_GENDOC_OUT",
        files=("docs/dev/reference/EVENTS.md",),
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
        note="the generated Mocking column, from the mock census",
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

    # UNGATED — a generated file nobody registered. The omission failure.
    registered = {rel for gen in generators for rel in gen.files}
    for rel in sorted(banner_bearing_files(root, scan_dirs) - registered):
        problems.append(
            f"UNGATED  {rel}: carries the GENERATED banner but no entry in GENERATORS"
            " owns it, so nothing checks whether it is current"
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

    print()
    print(
        f"{len(ran)}/{len(GENERATORS)} generators ran · {len(checked)} files compared"
        f" · {len(problems)} problem(s)"
    )
    if problems:
        print("Fix with:  python scripts/check_generated_docs.py --fix")
    return 1 if problems else 0


if __name__ == "__main__":
    sys.exit(main())
