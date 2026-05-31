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

It mounts the repo at `/workspace`, installs `requirements_test.txt`, and runs
pytest with whatever arguments you pass through.

```bat
@echo off
docker run --rm ^
  -v "%~dp0..:/workspace" ^
  -w /workspace ^
  python:3.14-slim ^
  bash -c "pip install -r requirements_test.txt -q && python -m pytest %*"
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

A known-good PowerShell invocation:

```powershell
docker run --rm `
  -v "C:\Users\CKing\Documents\GITHUB\eufy-vacuum-manager:/workspace" `
  -w /workspace `
  python:3.14-slim `
  sh -c "pip install -q -r requirements_test.txt && python -m pytest tests/ -q --no-header"
```

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
and writes an HTML report to `htmlcov/`. Both `htmlcov/` and the `.coverage`
data file are gitignored.

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

## First run is slow

The container does a fresh `pip install` on every invocation, so the first run
(and any run after the base image is pulled) spends ~20-30s installing before a
single test executes. The test execution itself is fast (the full suite runs in
well under a minute). If you are iterating tightly, run a single file to keep
the feedback loop short.
