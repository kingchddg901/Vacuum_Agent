# 02 — Running Tests

## The one rule: tests run in a Linux container

`pytest-homeassistant-custom-component` imports `fcntl`, a Unix-only stdlib
module. **It cannot run on Windows Python** — you get
`ModuleNotFoundError: No module named 'fcntl'`. Every test run goes through a
`python:3.14-slim` Docker container.

There is a runner for this:

```
scripts\test.bat
```

It runs pytest in the **pre-baked `eufy-vacuum-test` image** (the HA test deps
baked in — see [the locked-in image](#the-locked-in-image-no-pip-install-per-run)
below), mounting the repo at `/workspace` and passing through whatever arguments
you give it. No pip install per run.

```bat
@echo off
REM build the image once if it's missing, then reuse it
docker image inspect eufy-vacuum-test >nul 2>&1
if errorlevel 1 call "%~dp0build-test-image.bat" || exit /b 1
docker run --rm ^
  -v "%~dp0..:/workspace" ^
  -w /workspace ^
  eufy-vacuum-test ^
  python -m pytest %*
```

### Examples

```
scripts\test.bat                                          REM whole suite (unit + integration)
scripts\test.bat tests/integration/test_config_flow.py -v
scripts\test.bat --no-cov -k test_setup_flow
scripts\test.bat tests/unit                               REM just the unit layer
scripts\test.bat tests/adapters                           REM the adapter suite (not in default testpaths)
```

## Running it by hand (and the two Windows traps)

If you invoke Docker yourself instead of using `test.bat`, two things bite on
this machine:

1. **Use PowerShell, not Git Bash.** Git Bash rewrites the `-w /workspace`
   argument (POSIX-path mangling turns `/workspace` into a Windows path), and
   the container fails to find the working dir. Run Docker from PowerShell.
2. **Quote the volume mount with the absolute Windows path.**

A known-good PowerShell invocation (against the pre-baked image, no pip install):

```powershell
docker run --rm `
  -v "C:\Users\CKing\Documents\GITHUB\eufy-vacuum-manager:/workspace" `
  -w /workspace `
  eufy-vacuum-test `
  python -m pytest tests/ -q --no-header
```

(If you haven't built the image yet, run `scripts\build-test-image.bat` first,
or swap `eufy-vacuum-test` for `python:3.14-slim` and prefix the command with
`pip install -q -r requirements_test.txt &&` for a one-off zero-setup run.)

## Common flag recipes

| Goal | Flags |
|------|-------|
| Fast iteration on one file, no coverage | `tests/integration/test_x.py -q --no-header --no-cov` |
| Run one test by name | `-k test_name_substring` |
| Stop at first failure | `-x` |
| Short tracebacks | `--tb=short` |
| Coverage for specific modules only | `--cov=custom_components/eufy_vacuum/learning/manager --cov-report=term-missing` |
| Disable pytest cache (clean container) | `-p no:cacheprovider` |

`--no-cov` is worth using during iteration — coverage instrumentation slows the
run and clutters the output. The default `addopts` always turns coverage on, so
pass `--no-cov` to suppress it.

## Reading coverage

The default run prints a `term-missing` table (uncovered line numbers per file)
only — no HTML report is written. The `addopts` in `pytest.ini` enable just
`--cov-report=term-missing` and `--cov-branch`. To get an HTML report, ask for one
explicitly: pass `--cov-report=html:htmlcov_scratch` for a disposable report, or
`--cov-report=html:htmlcov` for the canonical regen. (Keeping `htmlcov/`
explicit-only means an incidental or sub-agent coverage run can never clobber it.)
Both `htmlcov/` and the `.coverage` data file are gitignored.

### Refreshing the numbers in these docs

The coverage percentages and test counts scattered through the testing docs
(per-module tables, the per-subsystem Cov column, the headline figures) are
maintained by a script so they don't drift. Run it inside the container:

```
docker run --rm -v "<repo>:/workspace" -w /workspace eufy-vacuum-test \
  python scripts/update_test_docs.py
```

It runs coverage, then rewrites only the numeric fields in place — prose, module
lists, and gap notes are never touched. Add `--dry-run` to preview, or `--no-run`
to reuse an existing `coverage.json`. Review the diff before committing.

### Per-file vs combined coverage

A module's coverage number depends on **which test files you run**. Example:
the pure-function helpers at the top of `learning/job_finalizer.py` are covered
by `tests/unit/test_learning_job_finalizer.py`. If you run only the integration
file, those lines show as missed and the percentage drops. To get the true
number for a module, run **all** files that exercise it:

```
scripts\test.bat tests/integration/test_learning_services.py tests/unit/test_learning_job_finalizer.py ^
  --cov=custom_components/eufy_vacuum/learning/job_finalizer --cov-report=term-missing
```

## The image-processing stack (numpy / scipy / Pillow)

The mapping segmentor pipeline depends on numpy, scipy, and Pillow:

- **numpy** arrives transitively through Home Assistant core, so it is always
  present.
- **scipy** and **Pillow** are **explicit entries in `requirements_test.txt`** —
  they are not pulled in by HA core. Without them the scipy/Pillow-dependent
  mapping code (`segment_primitives` transforms, `mask_edge_band`,
  `estimate_alignment`, the `eufy_cv` segmentor) can't be exercised.

Even so, scipy-only code paths should guard with
`pytest.importorskip("scipy.ndimage")` so a test file degrades to a skip rather
than an error if the stack is ever stripped from the environment:

```python
def test_mask_edge_band(np):
    pytest.importorskip("scipy.ndimage")
    ...
```

## The locked-in image (no pip install per run)

Installing `requirements_test.txt` fresh in the container costs ~1-2 min — far
longer than the suite itself (well under a minute). So the deps are **baked into
a local image once** and reused:

| File | Role |
|------|------|
| `scripts/test.Dockerfile` | `python:3.14-slim` + `pip install -r requirements_test.txt` |
| `scripts/build-test-image.bat` | builds/rebuilds the `eufy-vacuum-test` image |
| `scripts/test.bat` | runs pytest in that image (auto-builds it on first run) |

Lifecycle:

1. **First run** — `scripts\test.bat` sees no `eufy-vacuum-test` image and builds
   it once (the only slow run).
2. **Every run after** — reuses the image, so a test run is just `pytest` with no
   install step.
3. **After `requirements_test.txt` changes** — rebuild with
   `scripts\build-test-image.bat` (or delete the image and let `test.bat`
   rebuild it).

The image is ~1.4 GB and lives only on your machine — it is not committed; only
the Dockerfile + scripts are. Anyone who clones the repo gets the same baked
environment from the first `scripts\test.bat`.

> Iterating tightly? Run a single file (`scripts\test.bat tests/unit/test_x.py
> --no-cov`) — the image is already warm, so the only cost is the test itself.
