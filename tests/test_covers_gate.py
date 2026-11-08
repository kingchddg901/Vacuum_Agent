"""[CG-1..CG-6] The covers gate must FAIL on a test that lies about what it covers.

`scripts/check_covers.py` exists because six tests in this repo passed on 2026-11-07
without exercising what they named, four of them written that same day while closing
coverage gaps. A gate written in response to that cannot itself be taken on trust: a
gate with no demonstrated failure is a preference, and one that silently stops biting
is worse than none, because its green reads as proof.

So these drive the real script, as a subprocess, against SYNTHETIC trees built in
tmp_path -- the lying test cannot live in the real suite, which is exactly why the
script takes a `COVERS_ROOT` override. Each case asserts the EXIT CODE and the
reason, because a gate that fails for the wrong reason is not fenced either.

[CG-1] a test that does NOT execute its named symbol -> exit 1, UNCOVERED
[CG-2] the honest version of the same tree -> exit 0
[CG-3] a symbol that does not exist in the target -> exit 1, "does not exist"
[CG-4] a target with no `::symbol` (a line number, say) -> exit 1, MALFORMED
[CG-5] zero declarations -> exit 1, not a pass over an empty set
[CG-6] symbol_span resolves module functions and Class.method, and None for neither
[CG-7] a liar sharing a symbol with an HONEST test -> exit 1 (the v1 hole)
[CG-8] the gate leaves no coverage data in the tree it was pointed at (it used to,
       and then choked on its own leftovers on the next run)

[CG-7] IS THE ONE THE SUITE DID NOT HAVE. [CG-1] passed against v1 of the gate too,
because its lying test was ALONE in its group; an ablation on the real repo -- a
real marker repointed at a symbol its test never calls -- found that four honest
tests covered the span on the liar's behalf and the gate reported ok. One red input
was not enough, and the shape that was missing is the mixed group.

NOT FENCED HERE, named rather than left silent: the `no-sysmon-context` guard in
`run_coverage`. Forcing that warning means overriding the measurement core the gate
deliberately pins, so the only seam that would make it red is a test-only override
of the thing under test. It rests on measurement instead: under python 3.14's
default `core=sysmon` the warning fires and the report came back with FOUR context
names; with `COVERAGE_CORE=ctrace` the warning is gone and the same two tests
produce FIVE, the missing one being a `setup` phase. The data really was short.
"""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parents[1]
SCRIPT = REPO / "scripts" / "check_covers.py"

# The module under test in the synthetic tree. `used` is executed by the honest
# test; `never_used` is not executed by anything, which is what makes a claim on it
# a lie the gate has to catch.
_SRC = '''\
def used(n):
    doubled = n * 2
    return doubled


def never_used(n):
    tripled = n * 3
    return tripled
'''


def _tree(tmp_path: Path, test_body: str) -> Path:
    """A minimal repo-shaped tree: a package to measure and a test that claims it."""
    pkg = tmp_path / "pkg"
    pkg.mkdir()
    (pkg / "__init__.py").write_text("", encoding="utf-8")
    (pkg / "thing.py").write_text(_SRC, encoding="utf-8")
    tests = tmp_path / "tests"
    tests.mkdir()
    (tests / "__init__.py").write_text("", encoding="utf-8")
    (tests / "test_thing.py").write_text(test_body, encoding="utf-8")
    # An empty conftest at the tree root, which is what makes `pkg` importable:
    # pytest inserts the rootdir of the topmost conftest onto sys.path. Without it
    # the synthetic tests raise ImportError, pytest collects NOTHING, and `--cov`
    # then reports the un-imported module as fully missing -- so every claim reads
    # UNCOVERED and the gate fails for a reason that has nothing to do with the
    # claims. That is how the "inconclusive, not unmet" branch in the script came to
    # be written: this control case found it.
    #
    # It also REGISTERS THE MARKER. Without that the synthetic run raises
    # PytestUnknownMarkWarning, which errors, which trips the inconclusive branch --
    # so the tree has to be self-contained rather than leaning on this repo's
    # pytest.ini, which the inner run deliberately does not read.
    (tmp_path / "conftest.py").write_text(
        'def pytest_configure(config):\n'
        '    config.addinivalue_line(\n'
        '        "markers", "covers(target): the file.py::symbol this test covers"\n'
        '    )\n',
        encoding="utf-8",
    )
    # A MINIMAL pytest.ini is required, and not for taste. `pytest_asyncio` and
    # `pytest-homeassistant-custom-component` are installed as PLUGINS in this
    # environment, so their autouse fixtures apply to any pytest run here --
    # including this synthetic one. With no ini the asyncio mode is `strict`, and a
    # plain sync test that gets handed the plugin's autouse ASYNC fixture errors with
    # PytestRemovedIn9Warning before it runs. `auto` is what this repo's own
    # pytest.ini sets, so the tree matches the environment it executes in. The gate's
    # own command is untouched: it clears `addopts` but not the mode, which is
    # exactly right for real runs.
    (tmp_path / "pytest.ini").write_text(
        "[pytest]\n"
        "asyncio_mode = auto\n"
        "markers =\n"
        "    covers(target): the file.py::symbol this test covers\n",
        encoding="utf-8",
    )
    return tmp_path


def _run(root: Path) -> subprocess.CompletedProcess:
    return subprocess.run(
        [sys.executable, str(SCRIPT)],
        cwd=str(root), capture_output=True, text=True, timeout=300,
        env={**_env(), "COVERS_ROOT": str(root)},
    )


def _env() -> dict:
    import os
    return dict(os.environ)


_LYING = '''\
import pytest
from pkg.thing import used


@pytest.mark.covers("pkg/thing.py::never_used")
def test_calls_used_but_claims_never_used():
    assert used(2) == 4
'''

_HONEST = '''\
import pytest
from pkg.thing import never_used, used


@pytest.mark.covers("pkg/thing.py::used")
def test_calls_used():
    assert used(2) == 4


@pytest.mark.covers("pkg/thing.py::never_used")
def test_calls_never_used():
    assert never_used(2) == 6
'''

# TWO tests naming `used`, and only one of them calls it. The honest one covers the
# whole span, so a gate that judges the GROUP sees a fully covered symbol and says
# ok -- which is exactly what v1 did on the real repo.
_RIDER = '''\
import pytest
from pkg.thing import never_used, used


@pytest.mark.covers("pkg/thing.py::used")
def test_honestly_calls_used():
    assert used(2) == 4


@pytest.mark.covers("pkg/thing.py::used")
def test_rides_along_and_never_calls_used():
    assert never_used(2) == 6
'''


def test_cg1_a_test_that_does_not_execute_its_named_symbol_fails():
    """[CG-1] THE BITE. The test passes; the gate must still fail.

    This is the exact shape of LID-11 and LID-12: a green test whose named lines
    stayed missed. If this case ever goes green the gate has stopped working, and
    nothing else in the suite would notice -- which is the whole argument for
    testing a gate rather than trusting it.
    """
    import tempfile
    with tempfile.TemporaryDirectory() as td:
        root = _tree(Path(td), _LYING)
        proc = _run(root)

    assert proc.returncode == 1, (
        f"a lying claim must fail the gate.\nstdout:\n{proc.stdout}\n"
        f"stderr:\n{proc.stderr}"
    )
    assert "UNCOVERED" in proc.stdout, proc.stdout
    assert "never_used" in proc.stdout, proc.stdout


def test_cg2_the_honest_version_of_the_same_tree_passes():
    """[CG-2] The control, and it is not optional.

    Without it [CG-1] would pass just as happily if the gate failed on EVERYTHING --
    a gate that always fails is as useless as one that never does, and the
    difference is invisible from the failing case alone.
    """
    import tempfile
    with tempfile.TemporaryDirectory() as td:
        root = _tree(Path(td), _HONEST)
        proc = _run(root)

    assert proc.returncode == 0, (
        f"the honest tree must pass.\nstdout:\n{proc.stdout}\nstderr:\n{proc.stderr}"
    )
    assert "2 `covers` declaration(s)" in proc.stdout, proc.stdout


def test_cg3_a_symbol_that_does_not_exist_fails():
    """[CG-3] An unresolvable claim is a failure, never a skip.

    The lesson `doc_anchor.py`'s MALFORMED check was written from: a declaration
    nothing can parse does not fail validation, it becomes INVISIBLE, and invisible
    reads as clean. A typo'd symbol name must not quietly stop asserting.
    """
    import tempfile
    body = _LYING.replace("::never_used", "::no_such_function")
    with tempfile.TemporaryDirectory() as td:
        root = _tree(Path(td), body)
        proc = _run(root)

    assert proc.returncode == 1, proc.stdout
    assert "does not exist" in proc.stdout, proc.stdout


def test_cg4_a_target_without_a_symbol_is_malformed():
    """[CG-4] `file.py:120` is refused -- targets are symbols, never lines.

    Line citations rot. Inserting 21 comment lines into `dispatch/manager.py` moved
    its guards from 669/706 to 727/730 on the day this was written, and every line
    citation from that morning was wrong by the afternoon.
    `scripts/check_doc_citations.py` reached the same conclusion for docs.
    """
    import tempfile
    body = _LYING.replace('"pkg/thing.py::never_used"', '"pkg/thing.py:6"')
    with tempfile.TemporaryDirectory() as td:
        root = _tree(Path(td), body)
        proc = _run(root)

    assert proc.returncode == 1, proc.stdout
    assert "MALFORMED" in proc.stdout, proc.stdout
    assert "never a line" in proc.stdout, proc.stdout


def test_cg5_zero_declarations_is_a_failure_not_a_pass():
    """[CG-5] An empty set must not read as a pass.

    This repo has been bitten by exactly that: a status query that matched nothing
    counted 0 failures of 0 runs and reported CI green while two of five jobs were
    red. If the last marker is deleted, the gate is no longer protecting anything
    and must say so rather than exiting 0.
    """
    import tempfile
    body = "def test_nothing_declared():\n    assert True\n"
    with tempfile.TemporaryDirectory() as td:
        root = _tree(Path(td), body)
        proc = _run(root)

    assert proc.returncode == 1, proc.stdout
    assert "NOTHING DECLARED" in proc.stdout, proc.stdout


def test_cg7_a_liar_sharing_a_symbol_with_an_honest_test_still_fails():
    """[CG-7] The hole an ablation found, now fenced.

    v1 ran every test naming a symbol in ONE coverage run and asked whether the
    span came out covered. It did -- the honest test covers it -- so the rider's
    claim read as held. The two halves have to be judged separately: the SPAN is
    collective (several tests legitimately share one symbol, one per branch), the
    REACH is not.

    The assertion is deliberately BOTH facts: the span must still report `ok`, and
    the run must still fail. If the span went UNCOVERED here the case would be
    passing for the wrong reason -- that would be [CG-1] again, not this shape.
    """
    import tempfile
    with tempfile.TemporaryDirectory() as td:
        root = _tree(Path(td), _RIDER)
        proc = _run(root)

    assert "ok" in proc.stdout, (
        f"the span must still read ok -- the honest test does cover it. If it does "
        f"not, this case is re-testing CG-1.\nstdout:\n{proc.stdout}"
    )
    assert proc.returncode == 1, (
        f"the rider must fail the gate even though the span is covered.\n"
        f"stdout:\n{proc.stdout}\nstderr:\n{proc.stderr}"
    )
    assert "NEVER REACHES IT" in proc.stdout, proc.stdout
    assert "test_rides_along_and_never_calls_used" in proc.stdout, proc.stdout
    # and the honest one must NOT be blamed
    assert "test_honestly_calls_used  reaches" in proc.stdout, proc.stdout


def test_cg8_the_gate_leaves_no_coverage_data_behind():
    """[CG-8] The gate was SELF-POISONING, and running it twice is how that showed.

    coverage writes its data beside `COVERAGE_FILE`, which defaulted to whatever tree
    the gate was pointed at. Run the gate twice in this repo and the second run died:

        DataError: Couldn't use data file '.../.coverage...': no such table: context

    reported as an unhandled `FileNotFoundError` traceback on a temp path, naming
    nothing a reader could act on, because the report coverage never wrote was then
    `getsize`d. `run_coverage` now points `COVERAGE_FILE` at its own temp directory,
    so the gate neither reads nor leaves anything in the working tree, and the missing
    report is reported as INCONCLUSIVE rather than crashing.

    ⚠ THIS TEST PINS THE CAUSE, NOT THE SYMPTOM, and that is a deliberate retreat.
    A sibling case asserting the gate SURVIVES pre-existing stale data is not here: I
    wrote it, and could not make it fail. Planted zero-byte stubs did not reproduce
    the collision, nor did data generated by a real contextless `--cov` sweep in the
    synthetic tree -- pytest-cov erases the main data file before measuring, and
    whatever makes the repo's own leftovers reach the combiner does not reproduce
    under the generated config this gate runs with (`.coveragerc` sets no `parallel`,
    so that is not the discriminator either). Its red set is EMPTY and I cannot name
    the input, so it would have been a preference wearing a test's clothes.

    What IS verified: the gate now runs twice in a row in this repo, where it
    previously failed on the second run, and leaves nothing behind -- which is the
    only mechanism by which it could poison itself. Someone else's leftovers remain
    untested, and that is the honest limit.

    RED: drop the `COVERAGE_FILE` assignment in `run_coverage` and `.coverage` appears
    in the synthetic tree after the run.
    """
    import tempfile
    with tempfile.TemporaryDirectory() as td:
        root = _tree(Path(td), _HONEST)
        proc = _run(root)
        leftovers = sorted(p.name for p in root.iterdir()
                           if p.name.startswith(".coverage"))

    assert proc.returncode == 0, proc.stdout
    assert leftovers == [], f"the gate left coverage data behind: {leftovers}"


@pytest.mark.parametrize("symbol,expected", [
    ("used", True),
    ("never_used", True),
    ("MappingTracker._compact_dock_drift", False),   # wrong file for this symbol
    ("nope", False),
])
def test_cg6_symbol_span_resolves_what_it_claims_to(tmp_path, symbol, expected):
    """[CG-6] The resolver, directly: module functions, and a miss returning None.

    `Class.method` resolution is exercised against the REAL tree by the markers on
    `MappingTracker._compact_dock_drift`; here the negative row proves a symbol from
    another file does not accidentally resolve, which would make every claim on it
    pass for free.
    """
    sys.path.insert(0, str(REPO / "scripts"))
    try:
        import importlib
        mod = importlib.import_module("check_covers")
        importlib.reload(mod)
    finally:
        sys.path.pop(0)

    pkg = tmp_path / "pkg"
    pkg.mkdir()
    (pkg / "thing.py").write_text(_SRC, encoding="utf-8")
    mod.ROOT = str(tmp_path)

    span = mod.symbol_span("pkg/thing.py", symbol)
    assert (span is not None) is expected, f"{symbol!r} -> {span!r}"
    if expected:
        first, last = span
        assert first >= 1 and last >= first
