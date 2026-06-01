@echo off
REM Run the pytest suite inside a Linux container.
REM pytest-homeassistant-custom-component requires Linux (uses fcntl).
REM
REM Uses the pre-baked "eufy-vacuum-test" image (deps baked in) so test runs
REM skip the pip install. The image is built automatically on first run; rebuild
REM it after requirements_test.txt changes with scripts\build-test-image.bat.
REM
REM Usage:
REM   scripts\test.bat              run all tests
REM   scripts\test.bat tests/integration/test_config_flow.py -v
REM   scripts\test.bat --no-cov -k test_setup_flow

docker image inspect eufy-vacuum-test >nul 2>&1
if errorlevel 1 (
  echo [test.bat] eufy-vacuum-test image not found - building it once...
  call "%~dp0build-test-image.bat" || exit /b 1
)

docker run --rm ^
  -v "%~dp0..:/workspace" ^
  -w /workspace ^
  eufy-vacuum-test ^
  python -m pytest %*
