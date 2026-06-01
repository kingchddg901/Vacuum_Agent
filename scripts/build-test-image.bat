@echo off
REM Build (or rebuild) the pre-baked test image with the HA test deps baked in.
REM Run this once, then scripts\test.bat reuses the image with no pip install.
REM Rerun it after requirements_test.txt changes.
docker build -f "%~dp0test.Dockerfile" -t eufy-vacuum-test "%~dp0.."
