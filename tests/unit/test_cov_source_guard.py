"""Unit tests for the `--cov` source guard in tests/conftest.py.

The guard exists because a DOTTED `--cov` source reloads NumPy, after which every
`ndarray.sum()` raises `TypeError: float() argument must be a string or a real
number, not '_NoValueType'`. Measured 2026-11-07: 46 tests go red that way, none of
them related to the module being measured, and all of them green under `--no-cov`.
The full mechanism is recorded at tests/conftest.py::offending_cov_sources.

The rule is the PATH SEPARATOR, not existence: only a separator-free source reaches
coverage's `find_spec`, so a slash-bearing source is never flagged however wrong it
is. [COVG-1] is the test that pins that down, and it is there because an earlier
draft of the guard keyed on existence alone and rejected the repo's own documented
recipe -- a gate that refuses the documentation instead of the trap.

Coverage targets
----------------
[COVG-1] a slash-bearing source is accepted even when it does NOT exist as a path
         -- the false-positive regression (docs/testing/02-running-tests.md's own
         recipe is of exactly this shape).
[COVG-2] a dotted module name is flagged.
[COVG-3] a bare `--cov` (which arrives as True, not a source) is ignored.
[COVG-4] the hook resolves a separator-free source relative to rootdir, not just cwd.
[COVG-5] the repo's OWN pytest.ini sources pass -- the regression that matters, since
         the trap is one edit to addopts away.
[COVG-6] the HOOK raises, not merely the helper: pytest_configure is the wiring, and
         a correct helper with a disconnected hook would pass [COVG-1..5] untouched.
[COVG-7] the hook stays silent on the real addopts source (a false positive here
         would break every coverage run in the repo).
[COVG-8] a separator-free source that DOES exist as a path is accepted -- the only
         test that exercises the `path_exists` arm at all.
"""

from __future__ import annotations

import configparser
from pathlib import Path
from types import SimpleNamespace

import pytest

# Imported as a MODULE, not by name: `pytest_configure` is a hook name, and binding
# it into a test module's namespace invites it being treated as one.
from tests import conftest as tests_conftest

REPO_ROOT = Path(__file__).resolve().parents[2]
PYTEST_INI = REPO_ROOT / "pytest.ini"

DOTTED = "custom_components.eufy_vacuum.learning.external_run"
PATH_FORM = "custom_components/eufy_vacuum/learning/external_run.py"
# The shape docs/testing/02-running-tests.md uses: a slash path with no .py, so it
# does not exist. Harmless (it collects nothing) and must NOT be flagged.
DOCUMENTED_STEM = "custom_components/eufy_vacuum/learning/manager"


def _never(_text: str) -> bool:
    return False


def _only(*allowed: str):
    allowed_set = set(allowed)
    return lambda text: text in allowed_set


def _real_exists(text: str) -> bool:
    return Path(text).exists() or (REPO_ROOT / text).exists()


def _ini_cov_sources() -> list[str]:
    """The `--cov=` values pytest.ini actually sets.

    Deliberately NOT `startswith("--cov")` -- that also swallows `--cov-report=` and
    `--cov-branch`, and a filter that matched them would make this test assert
    something about flags that are not sources at all.
    """
    parser = configparser.ConfigParser()
    parser.read(PYTEST_INI, encoding="utf-8")
    addopts = parser["pytest"]["addopts"]
    return [
        line.strip().split("=", 1)[1].strip()
        for line in addopts.splitlines()
        if line.strip().startswith("--cov=")
    ]


def _fake_config(sources, root=REPO_ROOT):
    return SimpleNamespace(option=SimpleNamespace(cov_source=sources), rootpath=root)


# ---------------------------------------------------------------------------
# The helper
# ---------------------------------------------------------------------------

def test_a_slash_source_is_accepted_even_when_it_does_not_exist():
    """[COVG-1] the false-positive regression.

    `path_exists` is wired to refuse EVERYTHING here, so the only thing that can
    accept these is the separator rule. Both are real shapes: the documented stem
    carries no .py and so does not exist, and a non-existent path cannot be imported
    either way -- coverage just reports nothing for it.

    Keying the guard on existence alone (the first draft) turned this red and would
    have rejected the repo's own documented recipe at every invocation.
    """
    assert tests_conftest.offending_cov_sources(
        [DOCUMENTED_STEM, PATH_FORM], path_exists=_never
    ) == []
    # Windows-style separators count too -- scripts/test.bat passes those.
    assert tests_conftest.offending_cov_sources(
        [r"custom_components\eufy_vacuum\learning"], path_exists=_never
    ) == []


def test_a_dotted_module_name_is_flagged():
    """[COVG-2] the input that makes the guard fire -- the invocation that cost 46 reds."""
    assert tests_conftest.offending_cov_sources([DOTTED], path_exists=_never) == [DOTTED]


def test_a_bare_cov_flag_is_not_a_source():
    """[COVG-3] `--cov` with no value arrives as True; pytest-cov's own
    _prepare_cov_source documents that shape. Coercing it to a string would flag the
    literal "True" -- which has no separator and is not a path -- and so would refuse
    a perfectly ordinary invocation."""
    assert tests_conftest.offending_cov_sources([True], path_exists=_never) == []
    assert tests_conftest.offending_cov_sources(
        [True, DOTTED], path_exists=_never
    ) == [DOTTED]


def test_a_separator_free_source_that_exists_is_accepted():
    """[COVG-8] the `path_exists` arm.

    Every other accepting test passes via the separator rule, so without this one the
    existence check could be deleted outright and the file would stay green. A plain
    top-level package directory is the real case: `--cov=custom_components` is a
    legitimate invocation with no separator in it.
    """
    assert tests_conftest.offending_cov_sources(
        ["custom_components"], path_exists=_only("custom_components")
    ) == []
    assert tests_conftest.offending_cov_sources(
        ["custom_components"], path_exists=_never
    ) == ["custom_components"]


def test_the_repos_own_cov_sources_pass_the_guard():
    """[COVG-5] the regression this file is really for.

    Goes red if anyone rewrites pytest.ini's `--cov=` to a dotted module name, which
    is the one edit that reintroduces the trap for every contributor at once.
    """
    sources = _ini_cov_sources()
    # The denominator, stated: a parse that matched nothing would make the assertion
    # below pass over an empty set, which is not a pass.
    assert sources, f"parsed no --cov= sources out of {PYTEST_INI} -- the parse is wrong"
    assert tests_conftest.offending_cov_sources(sources, path_exists=_real_exists) == [], (
        f"pytest.ini declares a separator-free, non-existent --cov source: {sources!r}"
    )


# ---------------------------------------------------------------------------
# The hook (the wiring the helper's tests cannot see)
# ---------------------------------------------------------------------------

def test_the_hook_resolves_a_separator_free_source_relative_to_rootdir(tmp_path):
    """[COVG-4] rootdir resolution.

    The addopts source is rootdir-relative and pytest can be invoked from anywhere,
    so a cwd-only check would reject the repo's own configuration from any other
    directory. This has to go through the HOOK, not the helper: resolution is
    deliberately the hook's job so the helper stays disk-free.

    The source is separator-free on purpose -- a slash one would be accepted by the
    separator rule before `path_exists` was ever consulted, and the test would pass
    with the rootdir clause deleted. An earlier version made exactly that mistake.
    """
    (tmp_path / "pkg").mkdir()
    source = "pkg"
    assert not (Path.cwd() / source).exists(), (
        "the fixture is only meaningful while this source is absent from cwd"
    )
    tests_conftest.pytest_configure(_fake_config([source], root=tmp_path))  # must not raise


def test_the_hook_refuses_a_dotted_source():
    """[COVG-6] the helper is only useful if the hook calls it and raises."""
    with pytest.raises(pytest.UsageError) as excinfo:
        tests_conftest.pytest_configure(_fake_config([DOTTED]))
    message = str(excinfo.value)
    assert DOTTED in message, "the error must name the offending source"
    assert "-o addopts" in message, "the error must show the recipe that actually narrows"


def test_the_hook_accepts_the_real_addopts_source():
    """[COVG-7] and a false positive here would break every coverage run."""
    tests_conftest.pytest_configure(_fake_config(_ini_cov_sources()))
    # No cov_source at all (e.g. --no-cov, or pytest-cov absent) must also be fine.
    tests_conftest.pytest_configure(_fake_config(None))
