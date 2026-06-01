# Pre-baked test image for the eufy_vacuum suite.
#
# The HA test deps (pytest-homeassistant-custom-component, scipy, Pillow, …) are
# installed ONCE into this image so individual test runs skip the ~1-2 min pip
# install entirely. Build it with scripts\build-test-image.bat and rebuild only
# when requirements_test.txt changes.
#
# pytest-homeassistant-custom-component needs Linux (it imports fcntl), so the
# whole suite runs in this container — see docs/testing/02-running-tests.md.
FROM python:3.14-slim
WORKDIR /workspace
COPY requirements_test.txt /tmp/requirements_test.txt
RUN pip install --no-cache-dir -r /tmp/requirements_test.txt
