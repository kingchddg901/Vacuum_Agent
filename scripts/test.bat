@echo off
REM Run the pytest suite inside a Linux container.
REM pytest-homeassistant-custom-component requires Linux (uses fcntl).
REM
REM Usage:
REM   scripts\test.bat              run all tests
REM   scripts\test.bat tests/integration/test_config_flow.py -v
REM   scripts\test.bat --no-cov -k test_setup_flow

docker run --rm ^
  -v "%~dp0..:/workspace" ^
  -w /workspace ^
  python:3.14-slim ^
  bash -c "pip install -r requirements_test.txt -q && python -m pytest %*"
