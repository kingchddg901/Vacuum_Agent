"""Debug flight-recorder services — silent DEBUG capture + on-demand dump.

Four services, integration-global (not vacuum-scoped), all supports_response=True:

- ``debug_capture_start`` — begin silently capturing the integration's DEBUG into a
  bounded in-memory ring (optionally scoped to ``areas``, sized by ``size``).
- ``debug_capture_stop``  — stop; records survive for a final dump.
- ``debug_capture_dump``  — return the captured records and (default) write them to
  ``config/eufy_vacuum/debug/debug-<ts>.log`` for sharing.
- ``debug_capture_status`` — is it active, how much captured.

See :mod:`..debug_capture` for how the capture stays out of ``home-assistant.log``.
"""

from __future__ import annotations

import logging
import os
import time
from typing import Any

import voluptuous as vol

from homeassistant.core import HomeAssistant, ServiceCall
from homeassistant.helpers import config_validation as cv

from ..const import (
    DOMAIN,
    SERVICE_DEBUG_CAPTURE_DUMP,
    SERVICE_DEBUG_CAPTURE_START,
    SERVICE_DEBUG_CAPTURE_STATUS,
    SERVICE_DEBUG_CAPTURE_STOP,
)
from ..debug_capture import MAX_CAPACITY, get_capture, render_text

_LOGGER = logging.getLogger(__name__)


SERVICES = (
    SERVICE_DEBUG_CAPTURE_START,
    SERVICE_DEBUG_CAPTURE_STOP,
    SERVICE_DEBUG_CAPTURE_DUMP,
    SERVICE_DEBUG_CAPTURE_STATUS,
)


_START_SCHEMA = vol.Schema(
    {
        vol.Optional("areas"): vol.All(cv.ensure_list, [cv.string]),
        vol.Optional("size"): vol.All(vol.Coerce(int), vol.Range(min=1, max=MAX_CAPACITY)),
    }
)
_DUMP_SCHEMA = vol.Schema(
    {
        vol.Optional("write_file", default=True): cv.boolean,
        vol.Optional("clear", default=False): cv.boolean,
    }
)
_EMPTY_SCHEMA = vol.Schema({})


def _write_dump(hass: HomeAssistant, records: list[dict[str, Any]]) -> str:
    """Write the rendered ring to a timestamped file; return its path. Blocking —
    call via the executor."""
    dir_path = hass.config.path("eufy_vacuum", "debug")
    os.makedirs(dir_path, exist_ok=True)
    ts = time.strftime("%Y%m%d-%H%M%S", time.localtime())
    path = os.path.join(dir_path, f"debug-{ts}.log")
    with open(path, "w", encoding="utf-8") as handle:
        handle.write(render_text(records))
    return path


def register(hass: HomeAssistant) -> None:
    """Register the debug flight-recorder services."""

    async def start(call: ServiceCall) -> dict[str, Any]:
        status = get_capture().start(
            areas=call.data.get("areas"), capacity=call.data.get("size")
        )
        # INFO so the "capture is on" breadcrumb still reaches home-assistant.log
        # (via the passthrough) — a user reading the main log sees capture is active.
        _LOGGER.info("eufy_vacuum debug capture STARTED: %s", status)
        return status

    async def stop(call: ServiceCall) -> dict[str, Any]:
        status = get_capture().stop()
        _LOGGER.info(
            "eufy_vacuum debug capture STOPPED (captured=%s)", status.get("captured")
        )
        return status

    async def dump(call: ServiceCall) -> dict[str, Any]:
        capture = get_capture()
        records = capture.records()
        result: dict[str, Any] = {
            "active": capture.active,
            "count": len(records),
            "records": records,
        }
        if call.data.get("write_file", True):
            result["file"] = await hass.async_add_executor_job(_write_dump, hass, records)
        if call.data.get("clear", False):
            capture.clear()
        return result

    async def status(call: ServiceCall) -> dict[str, Any]:
        return get_capture().status()

    hass.services.async_register(
        DOMAIN, SERVICE_DEBUG_CAPTURE_START, start,
        schema=_START_SCHEMA, supports_response=True,
    )
    hass.services.async_register(
        DOMAIN, SERVICE_DEBUG_CAPTURE_STOP, stop,
        schema=_EMPTY_SCHEMA, supports_response=True,
    )
    hass.services.async_register(
        DOMAIN, SERVICE_DEBUG_CAPTURE_DUMP, dump,
        schema=_DUMP_SCHEMA, supports_response=True,
    )
    hass.services.async_register(
        DOMAIN, SERVICE_DEBUG_CAPTURE_STATUS, status,
        schema=_EMPTY_SCHEMA, supports_response=True,
    )
