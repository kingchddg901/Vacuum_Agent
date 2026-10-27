@echo off
REM Build (or rebuild) the pre-baked test image with the HA test deps baked in.
REM Run this once, then scripts\test.bat reuses the image with no pip install.
REM
REM --pull --no-cache IS LOAD-BEARING, do not drop it to save two minutes.
REM test.Dockerfile says to rebuild when the RESOLVED versions drift, not when
REM requirements_test.txt changes -- every requirement there is a >= floor and CI
REM pip-installs fresh on every job. Without these flags that rebuild is a no-op:
REM the requirements file is unchanged, so Docker serves the cached pip layer and
REM reports success. Measured 2026-10-26 cutting 2.5.1 -- a plain rebuild left the
REM image on homeassistant 2026.10.2 / p-h-c-c 0.13.373 while a fresh install
REM resolved 2026.10.4 / 0.13.375, i.e. exactly the frozen-image lie the Dockerfile
REM header describes, produced by the command it tells you to run.
REM
REM Compare against a FRESH RESOLVE, never against the newest version on PyPI:
REM pytest-homeassistant-custom-component pins homeassistant, pytest, pytest-asyncio
REM and numpy exactly, so "pytest 9.1.1 is out" is not drift -- 0.13.375 pins 9.0.3
REM and that is what CI gets too. Pillow is NOT pinned there and still resolves to
REM 12.3.0 rather than 13.0.0 on python:3.14-slim (wheel availability), so grading
REM the image against PyPI latest reports drift that does not exist.
docker build --pull --no-cache -f "%~dp0test.Dockerfile" -t eufy-vacuum-test "%~dp0.."
