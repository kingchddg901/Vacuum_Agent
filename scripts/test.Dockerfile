# Pre-baked test image for the eufy_vacuum suite.
#
# The HA test deps (pytest-homeassistant-custom-component, scipy, Pillow, …) are
# installed ONCE into this image so individual test runs skip the ~1-2 min pip
# install entirely. Build it with scripts\build-test-image.bat and rebuild only
# when requirements_test.txt changes.
#
# ^ THAT TRIGGER IS WRONG, AND IT COST A RELEASE. Every requirement here is a `>=`
# FLOOR and CI runs a fresh `pip install` on every job, so CI tracks the latest
# release while a baked image stays frozen at whatever shipped the day it was
# built. This file can go untouched for weeks while the two diverge by a whole
# Home Assistant version. REBUILD WHEN THE RESOLVED VERSIONS DRIFT, NOT WHEN THIS
# FILE CHANGES.
#
# 2026-09-13: this image sat on homeassistant 2026.8.0 while CI had moved on; HA
# turned `device_registry.async_get_device` from deprecated into a RuntimeError;
# a local run reported 4921 PASSED against a CI run that FAILED. A green local
# suite meant nothing, and nothing said so.
#
# Check before trusting a local green:
#   docker run --rm eufy-vacuum-test python -c #     "from importlib.metadata import version; print(version('homeassistant'))"
#
# pytest-homeassistant-custom-component needs Linux (it imports fcntl), so the
# whole suite runs in this container — see docs/testing/02-running-tests.md.
FROM python:3.14-slim
WORKDIR /workspace
COPY requirements_test.txt /tmp/requirements_test.txt
RUN pip install --no-cache-dir -r /tmp/requirements_test.txt
